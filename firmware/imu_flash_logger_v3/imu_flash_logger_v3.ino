#include "ICM_20948.h"
#include <LittleFS.h>
#include <esp_timer.h>

#define I2C_SDA_PIN 8
#define I2C_SCL_PIN 9
#define AD0_VAL 0
#define I2C_CLOCK_HZ 50000UL
#define SERIAL_BAUD 230400

#define BOOT_BUTTON_PIN 0
#define CAPTURE_SECONDS 10
#define MAX_CONSECUTIVE_FAULTS 5
#define COMMAND_BUFFER_SIZE 64

ICM_20948_I2C myICM;

uint32_t totalErrors = 0;
uint32_t totalResets = 0;
uint16_t consecutiveFaults = 0;
uint32_t lastButtonChangeMs = 0;
bool buttonWasDown = false;
char commandBuffer[COMMAND_BUFFER_SIZE];
size_t commandLength = 0;

static int16_t be16(const uint8_t *data) {
  return (int16_t)(((uint16_t)data[0] << 8) | data[1]);
}

static bool configureImu() {
  ICM_20948_Status_e status;

  status = myICM.setSampleMode(
      ICM_20948_Internal_Acc | ICM_20948_Internal_Gyr,
      ICM_20948_Sample_Mode_Continuous);
  if (status != ICM_20948_Stat_Ok) {
    Serial.printf("CONFIG_ERR,sample_mode,%s\n", myICM.statusString(status));
    return false;
  }

  ICM_20948_fss_t fullScale;
  fullScale.a = gpm16;
  fullScale.g = dps2000;
  status = myICM.setFullScale(
      ICM_20948_Internal_Acc | ICM_20948_Internal_Gyr,
      fullScale);
  if (status != ICM_20948_Stat_Ok) {
    Serial.printf("CONFIG_ERR,full_scale,%s\n", myICM.statusString(status));
    return false;
  }

  ICM_20948_dlpcfg_t dlpf;
  dlpf.a = acc_d111bw4_n136bw;
  dlpf.g = gyr_d119bw5_n154bw3;
  status = myICM.setDLPFcfg(
      ICM_20948_Internal_Acc | ICM_20948_Internal_Gyr,
      dlpf);
  if (status != ICM_20948_Stat_Ok) {
    Serial.printf("CONFIG_ERR,dlpf_cfg,%s\n", myICM.statusString(status));
    return false;
  }

  status = myICM.enableDLPF(ICM_20948_Internal_Acc, true);
  if (status != ICM_20948_Stat_Ok) {
    Serial.printf("CONFIG_ERR,dlpf_acc_enable,%s\n", myICM.statusString(status));
    return false;
  }

  status = myICM.enableDLPF(ICM_20948_Internal_Gyr, true);
  if (status != ICM_20948_Stat_Ok) {
    Serial.printf("CONFIG_ERR,dlpf_gyr_enable,%s\n", myICM.statusString(status));
    return false;
  }

  ICM_20948_smplrt_t sampleRate;
  sampleRate.a = 4;
  sampleRate.g = 4;
  status = myICM.setSampleRate(
      ICM_20948_Internal_Acc | ICM_20948_Internal_Gyr,
      sampleRate);
  if (status != ICM_20948_Stat_Ok) {
    Serial.printf("CONFIG_ERR,sample_rate,%s\n", myICM.statusString(status));
    return false;
  }

  status = myICM.setBank(0);
  if (status != ICM_20948_Stat_Ok) {
    Serial.printf("CONFIG_ERR,bank,%s\n", myICM.statusString(status));
    return false;
  }

  Serial.println(
      "IMU_CONFIG,acc=16g,gyro=2000dps,acc_dlpf=111.4Hz,"
      "gyr_dlpf=119.5Hz,odr_acc=225Hz,odr_gyr=220Hz,i2c=50000,addr=0x68");
  return true;
}

static bool initializeImu() {
  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);
  Wire.setClock(I2C_CLOCK_HZ);

  myICM.begin(Wire, AD0_VAL);
  Serial.printf("IMU_INIT,status=%s\n", myICM.statusString());

  if (myICM.status != ICM_20948_Stat_Ok) {
    return false;
  }

  if (!configureImu()) {
    return false;
  }

  consecutiveFaults = 0;
  return true;
}

static bool mountFileSystem() {
  Serial.println("FILESYSTEM_MOUNTING");

  if (LittleFS.begin(false, "/littlefs", 10, "spiffs")) {
    Serial.println("FILESYSTEM_MOUNT_OK");
    return true;
  }

  Serial.println("FILESYSTEM_MOUNT_FAILED,formatting");
  if (!LittleFS.format()) {
    Serial.println("FILESYSTEM_FORMAT_FAILED");
    return false;
  }

  Serial.println("FILESYSTEM_FORMAT_OK");
  delay(100);

  if (!LittleFS.begin(false, "/littlefs", 10, "spiffs")) {
    Serial.println("FILESYSTEM_REMOUNT_FAILED");
    return false;
  }

  Serial.println("FILESYSTEM_MOUNT_OK");
  return true;
}

static void reportFault(ICM_20948_Status_e status, int64_t timestampUs) {
  totalErrors++;
  consecutiveFaults++;

  Serial.printf(
      "ERR,ts_us=%lld,status=%s,fault=%u,total=%lu\n",
      (long long)timestampUs,
      myICM.statusString(status),
      consecutiveFaults,
      (unsigned long)totalErrors);

  if (consecutiveFaults < MAX_CONSECUTIVE_FAULTS) {
    return;
  }

  totalResets++;
  Serial.printf(
      "RESET,ts_us=%lld,reason=%s,count=%lu\n",
      (long long)timestampUs,
      myICM.statusString(status),
      (unsigned long)totalResets);

  Wire.end();
  delay(50);

  if (initializeImu()) {
    Serial.printf(
        "RESET_OK,ts_us=%lld,count=%lu\n",
        (long long)esp_timer_get_time(),
        (unsigned long)totalResets);
  } else {
    Serial.printf(
        "RESET_FAILED,ts_us=%lld,count=%lu\n",
        (long long)esp_timer_get_time(),
        (unsigned long)totalResets);
  }
}

static bool isCaptureFile(const char *name) {
  const String filename = String(name);
  return filename.startsWith("/capture_") && filename.endsWith(".csv");
}

static bool findNextCapturePath(char *path, size_t pathSize) {
  for (uint16_t index = 1; index < 1000; index++) {
    snprintf(path, pathSize, "/capture_%03u.csv", index);
    if (!LittleFS.exists(path)) {
      return true;
    }
  }
  return false;
}

static void printFileList() {
  File root = LittleFS.open("/");
  if (!root) {
    Serial.println("LIST_ERROR");
    return;
  }

  File entry = root.openNextFile();
  while (entry) {
    String name = entry.name();
    if (!name.startsWith("/")) {
      name = "/" + name;
    }
    if (!entry.isDirectory() && isCaptureFile(name.c_str())) {
      Serial.printf("FILE,%s,%lu\n", name.c_str(), (unsigned long)entry.size());
    }
    entry = root.openNextFile();
  }
  root.close();
  Serial.println("LIST_END");
}

static void dumpFile(const char *path) {
  if (!isCaptureFile(path)) {
    Serial.println("DUMP_ERROR,invalid_name");
    return;
  }

  File file = LittleFS.open(path, FILE_READ);
  if (!file) {
    Serial.println("DUMP_ERROR,not_found");
    return;
  }

  Serial.printf(
      "BEGIN_FILE,%s,%lu\n",
      path,
      (unsigned long)file.size());
  Serial.flush();

  uint8_t buffer[256];
  while (file.available()) {
    const size_t count = file.read(buffer, sizeof(buffer));
    if (count == 0) {
      break;
    }
    Serial.write(buffer, count);
  }

  file.close();
  Serial.flush();
  Serial.println();
  Serial.println("END_FILE");
}

static void deleteFile(const char *path) {
  if (!isCaptureFile(path)) {
    Serial.println("DELETE_ERROR,invalid_name");
    return;
  }
  if (!LittleFS.exists(path)) {
    Serial.println("DELETE_ERROR,not_found");
    return;
  }
  if (LittleFS.remove(path)) {
    Serial.printf("DELETE_OK,%s\n", path);
  } else {
    Serial.printf("DELETE_ERROR,%s\n", path);
  }
}

static bool recordCapture() {
  char path[32];
  if (!findNextCapturePath(path, sizeof(path))) {
    Serial.println("CAPTURE_ERROR,no_filename");
    return false;
  }

  File file = LittleFS.open(path, FILE_WRITE);
  if (!file) {
    Serial.printf("CAPTURE_ERROR,open_failed,%s\n", path);
    return false;
  }

  const int64_t startUs = esp_timer_get_time();
  const int64_t endUs = startUs + (int64_t)CAPTURE_SECONDS * 1000000;
  const uint32_t errorsAtStart = totalErrors;
  const uint32_t resetsAtStart = totalResets;
  uint32_t rows = 0;
  bool writeFailed = false;

  file.println("seq,timestamp_us,ax_mg,ay_mg,az_mg,gx_dps,gy_dps,gz_dps,temp_c");
  Serial.printf(
      "CAPTURE_START,file=%s,seconds=%u\n",
      path,
      CAPTURE_SECONDS);

  while (esp_timer_get_time() < endUs) {
    if (!myICM.dataReady()) {
      const ICM_20948_Status_e readyStatus = myICM.status;
      if (readyStatus != ICM_20948_Stat_Ok &&
          readyStatus != ICM_20948_Stat_NoData) {
        reportFault(readyStatus, esp_timer_get_time());
      }
      delay(1);
      continue;
    }

    uint8_t raw[14];
    const int64_t timestampUs = esp_timer_get_time();
    const ICM_20948_Status_e status =
        myICM.read((uint8_t)AGB0_REG_ACCEL_XOUT_H, raw, sizeof(raw));

    if (status != ICM_20948_Stat_Ok) {
      reportFault(status, timestampUs);
      continue;
    }

    consecutiveFaults = 0;

    const int16_t rawAx = be16(&raw[0]);
    const int16_t rawAy = be16(&raw[2]);
    const int16_t rawAz = be16(&raw[4]);
    const int16_t rawGx = be16(&raw[6]);
    const int16_t rawGy = be16(&raw[8]);
    const int16_t rawGz = be16(&raw[10]);
    const int16_t rawTemp = be16(&raw[12]);

    const size_t written = file.printf(
        "%lu,%lld,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f\n",
        (unsigned long)rows,
        (long long)timestampUs,
        rawAx / 2.048f,
        rawAy / 2.048f,
        rawAz / 2.048f,
        rawGx / 16.4f,
        rawGy / 16.4f,
        rawGz / 16.4f,
        ((float)rawTemp - 21.0f) / 333.87f + 21.0f);

    if (written == 0) {
      writeFailed = true;
      break;
    }
    rows++;
  }

  const int64_t endTimeUs = esp_timer_get_time();
  file.flush();
  file.close();

  Serial.printf(
      "CAPTURE_DONE,file=%s,rows=%lu,duration_ms=%.1f,"
      "errors=%lu,resets=%lu,write_failed=%u\n",
      path,
      (unsigned long)rows,
      (double)(endTimeUs - startUs) / 1000.0,
      (unsigned long)(totalErrors - errorsAtStart),
      (unsigned long)(totalResets - resetsAtStart),
      writeFailed ? 1 : 0);

  return rows > 0 && !writeFailed;
}

static void handleCommand(char *command) {
  while (*command == ' ') {
    command++;
  }

  if (strcmp(command, "LIST") == 0) {
    printFileList();
    return;
  }

  if (strcmp(command, "START") == 0) {
    recordCapture();
    return;
  }

  if (strcmp(command, "INFO") == 0) {
    Serial.printf(
        "INFO,filesystem_total=%lu,filesystem_used=%lu\n",
        (unsigned long)LittleFS.totalBytes(),
        (unsigned long)LittleFS.usedBytes());
    return;
  }

  if (strncmp(command, "DUMP ", 5) == 0) {
    dumpFile(command + 5);
    return;
  }

  if (strncmp(command, "DELETE ", 7) == 0) {
    deleteFile(command + 7);
    return;
  }

  Serial.println("COMMAND_ERROR");
}

static void pollSerialCommands() {
  while (Serial.available()) {
    const char value = (char)Serial.read();
    if (value == '\r' || value == '\n') {
      if (commandLength > 0) {
        commandBuffer[commandLength] = '\0';
        handleCommand(commandBuffer);
        commandLength = 0;
      }
      continue;
    }

    if (commandLength < COMMAND_BUFFER_SIZE - 1) {
      commandBuffer[commandLength++] = value;
    }
  }
}

static bool consumeButtonPress() {
  const bool isDown = digitalRead(BOOT_BUTTON_PIN) == LOW;
  const uint32_t now = millis();

  if (isDown != buttonWasDown && now - lastButtonChangeMs >= 50) {
    lastButtonChangeMs = now;
    buttonWasDown = isDown;
    return isDown;
  }

  return false;
}

void setup() {
  Serial.begin(SERIAL_BAUD);
  delay(1000);
  Serial.println("IMU_FLASH_V3_BOOT");

  pinMode(BOOT_BUTTON_PIN, INPUT_PULLUP);
  buttonWasDown = digitalRead(BOOT_BUTTON_PIN) == LOW;
  lastButtonChangeMs = millis();

  if (!mountFileSystem()) {
    Serial.println("FILESYSTEM_ERROR");
    while (true) {
      delay(1000);
    }
  }

  Serial.printf(
      "FILESYSTEM,free=%lu,total=%lu\n",
      (unsigned long)(LittleFS.totalBytes() - LittleFS.usedBytes()),
      (unsigned long)LittleFS.totalBytes());

  uint8_t attempts = 0;
  while (!initializeImu() && attempts < 5) {
    attempts++;
    Serial.printf("IMU_INIT_RETRY,attempt=%u\n", attempts);
    delay(500);
  }

  if (myICM.status != ICM_20948_Stat_Ok) {
    Serial.println("IMU_FLASH_V3_FATAL");
    while (true) {
      delay(1000);
    }
  }

  Serial.println("IMU_FLASH_V3_READY");
  Serial.println(
      "Commands: LIST, INFO, START, DUMP /capture_001.csv, "
      "DELETE /capture_001.csv");
}

void loop() {
  pollSerialCommands();

  if (consumeButtonPress()) {
    recordCapture();
  }

  delay(5);
}
