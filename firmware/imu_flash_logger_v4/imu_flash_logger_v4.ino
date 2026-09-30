#include "ICM_20948.h"
#include <LittleFS.h>
#include <esp_timer.h>
#include <stdlib.h>

#define ENABLE_BLE_CONTROL 1

#if ENABLE_BLE_CONTROL
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#endif

#ifdef RGB_BUILTIN
#define STATUS_LED_PIN RGB_BUILTIN
#else
#define STATUS_LED_PIN 48
#endif

#define I2C_SDA_PIN 8
#define I2C_SCL_PIN 9
#define AD0_VAL 0
#define I2C_CLOCK_HZ 50000UL
#define SERIAL_BAUD 230400

#define BOOT_BUTTON_PIN 0
#define CAPTURE_SECONDS 10
#define MIN_VALID_ROWS 1000
#define BUTTON_STARTUP_ARM_MS 3000
#define BUTTON_HOLD_MS 1000
#define MAX_CONSECUTIVE_FAULTS 5
#define COMMAND_BUFFER_SIZE 64
#define MAX_SAMPLES (CAPTURE_SECONDS * 260 + 100)
#define MIN_FREE_BYTES 300000UL
#define TELEMETRY_MAX_SAMPLES 4

#if ENABLE_BLE_CONTROL
#define BLE_DEVICE_NAME "KineShoot-Cam"
#define BLE_CONTROL_SERVICE_UUID "6b1d0001-9a3f-4d2a-8f6f-6b1d00000001"
#define BLE_CONTROL_CHARACTERISTIC_UUID "6b1d0002-9a3f-4d2a-8f6f-6b1d00000002"
#endif

ICM_20948_I2C myICM;

struct RawSample {
  int64_t timestampUs;
  int16_t ax;
  int16_t ay;
  int16_t az;
  int16_t gx;
  int16_t gy;
  int16_t gz;
  int16_t temp;
};

struct TelemetrySample {
  uint32_t elapsedMs;
  uint32_t freeBytes;
};

uint32_t totalErrors = 0;
uint32_t totalResets = 0;
uint16_t consecutiveFaults = 0;
uint32_t lastButtonChangeMs = 0;
bool buttonCaptureLatched = false;
uint32_t buttonDownSinceMs = 0;
uint32_t captureArmedAtMs = 0;
char commandBuffer[COMMAND_BUFFER_SIZE];
size_t commandLength = 0;

#if ENABLE_BLE_CONTROL
volatile bool bleCapturePending = false;

class KineShootBleServerCallbacks : public BLEServerCallbacks {
  void onConnect(BLEServer *server) override {
    (void)server;
    Serial.println("BLE_CONNECTED");
  }

  void onDisconnect(BLEServer *server) override {
    (void)server;
    Serial.println("BLE_DISCONNECTED");
    BLEDevice::getAdvertising()->start();
  }
};

class KineShootBleCommandCallbacks : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic *characteristic) override {
    const String value = characteristic->getValue();
    if (value.length() == 0) {
      return;
    }
    const uint8_t command = (uint8_t)value[0];
    if (command == 0x01) {
      bleCapturePending = true;
      Serial.println("BLE_COMMAND,capture");
    } else if (command == 0x02) {
      bleCapturePending = true;
      Serial.println("BLE_COMMAND,capture_and_video");
    }
  }
};
#endif

static int16_t be16(const uint8_t *data) {
  return (int16_t)(((uint16_t)data[0] << 8) | data[1]);
}

static void setStatusColor(uint8_t red, uint8_t green, uint8_t blue) {
  rgbLedWrite(STATUS_LED_PIN, red, green, blue);
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

static bool isPrimaryCaptureFile(const char *name) {
  const String filename = String(name);
  return filename.startsWith("/capture_") && filename.endsWith(".csv") &&
         !filename.endsWith(".telemetry.csv");
}

static bool findNextCapturePath(char *path, size_t pathSize) {
  uint16_t maxIndex = 0;
  File root = LittleFS.open("/");
  if (!root) {
    return false;
  }

  File entry = root.openNextFile();
  while (entry) {
    String name = entry.name();
    if (!name.startsWith("/")) {
      name = "/" + name;
    }
    if (!entry.isDirectory() && isPrimaryCaptureFile(name.c_str())) {
      unsigned int index = 0;
      if (sscanf(name.c_str(), "/capture_%u.csv", &index) == 1 && index < 1000) {
        if (index > maxIndex) {
          maxIndex = (uint16_t)index;
        }
      }
    }
    entry = root.openNextFile();
  }
  root.close();

  const uint16_t nextIndex = maxIndex + 1;
  if (nextIndex >= 1000) {
    return false;
  }
  snprintf(path, pathSize, "/capture_%03u.csv", nextIndex);
  return true;
}

static bool isInvalidCaptureFile(const char *path) {
  File file = LittleFS.open(path, FILE_READ);
  if (!file) {
    return false;
  }
  if (file.size() == 0) {
    file.close();
    return true;
  }
  const String header = file.readStringUntil('\n');
  const String firstDataLine = file.readStringUntil('\n');
  file.close();
  return header.length() > 0 && firstDataLine.length() == 0;
}

static void cleanupInvalidCaptureFiles() {
  char paths[64][40];
  uint8_t count = 0;

  File root = LittleFS.open("/");
  if (!root) {
    return;
  }
  File entry = root.openNextFile();
  while (entry) {
    String name = entry.name();
    if (!name.startsWith("/")) {
      name = "/" + name;
    }
    if (!entry.isDirectory() && isCaptureFile(name.c_str()) && count < 64 &&
        isInvalidCaptureFile(name.c_str())) {
      strlcpy(paths[count], name.c_str(), sizeof(paths[count]));
      count++;
    }
    entry = root.openNextFile();
  }
  root.close();

  uint8_t removed = 0;
  for (uint8_t index = 0; index < count; index++) {
    if (LittleFS.remove(paths[index])) {
      removed++;
      Serial.printf("CLEANUP_REMOVED,%s\n", paths[index]);
    }
  }
  Serial.printf("CLEANUP,invalid=%u,removed=%u\n", count, removed);
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
    delay(1);
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

static void appendTelemetrySample(
    TelemetrySample *samples,
    uint32_t &count,
    uint32_t elapsedMs) {
  if (count >= TELEMETRY_MAX_SAMPLES) {
    return;
  }
  samples[count].elapsedMs = elapsedMs;
  samples[count].freeBytes =
      (uint32_t)(LittleFS.totalBytes() - LittleFS.usedBytes());
  count++;
}

static void buildTelemetryPath(
    const char *capturePath,
    char *telemetryPath,
    size_t telemetryPathSize) {
  snprintf(telemetryPath, telemetryPathSize, "%s", capturePath);
  char *dot = strrchr(telemetryPath, '.');
  if (dot != NULL) {
    strcpy(dot, ".telemetry.csv");
  }
}

static bool recordCapture() {
  char path[32];
  if (!findNextCapturePath(path, sizeof(path))) {
    Serial.println("CAPTURE_ERROR,no_filename");
    return false;
  }

  const size_t freeBytes = LittleFS.totalBytes() - LittleFS.usedBytes();
  if (freeBytes < MIN_FREE_BYTES) {
    Serial.printf(
        "CAPTURE_ERROR,low_space,free=%lu,required=%lu\n",
        (unsigned long)freeBytes,
        (unsigned long)MIN_FREE_BYTES);
    return false;
  }

  const size_t freeAtStart = freeBytes;
  TelemetrySample telemetry[TELEMETRY_MAX_SAMPLES];
  uint32_t telemetryRows = 0;

  RawSample *samples = (RawSample *)malloc(sizeof(RawSample) * MAX_SAMPLES);
  if (samples == NULL) {
    Serial.println("CAPTURE_ERROR,memory");
    return false;
  }

  setStatusColor(64, 0, 0);
  const int64_t startUs = esp_timer_get_time();
  const int64_t endUs = startUs + (int64_t)CAPTURE_SECONDS * 1000000;
  const uint32_t errorsAtStart = totalErrors;
  const uint32_t resetsAtStart = totalResets;
  uint32_t rows = 0;
  uint32_t noDataPolls = 0;
  uint32_t noDataReads = 0;
  bool writeFailed = false;

  Serial.printf(
      "CAPTURE_START,file=%s,seconds=%u\n",
      path,
      CAPTURE_SECONDS);
  appendTelemetrySample(telemetry, telemetryRows, 0);

  while (esp_timer_get_time() < endUs) {
    if (!myICM.dataReady()) {
      const ICM_20948_Status_e readyStatus = myICM.status;
      if (readyStatus == ICM_20948_Stat_NoData) {
        noDataPolls++;
      } else if (readyStatus != ICM_20948_Stat_Ok) {
        reportFault(readyStatus, esp_timer_get_time());
      }
      delay(1);
      continue;
    }

    uint8_t raw[14];
    const int64_t timestampUs = esp_timer_get_time();
    const ICM_20948_Status_e status =
        myICM.read((uint8_t)AGB0_REG_ACCEL_XOUT_H, raw, sizeof(raw));

    if (status == ICM_20948_Stat_NoData) {
      noDataReads++;
      continue;
    }

    if (status != ICM_20948_Stat_Ok) {
      reportFault(status, timestampUs);
      continue;
    }

    consecutiveFaults = 0;

    if (rows < MAX_SAMPLES) {
      samples[rows].timestampUs = timestampUs;
      samples[rows].ax = be16(&raw[0]);
      samples[rows].ay = be16(&raw[2]);
      samples[rows].az = be16(&raw[4]);
      samples[rows].gx = be16(&raw[6]);
      samples[rows].gy = be16(&raw[8]);
      samples[rows].gz = be16(&raw[10]);
      samples[rows].temp = be16(&raw[12]);
      rows++;
    }
  }

  const int64_t endTimeUs = esp_timer_get_time();
  const int64_t writeStartUs = esp_timer_get_time();

  if (rows < MIN_VALID_ROWS) {
    if (LittleFS.exists(path)) {
      LittleFS.remove(path);
    }
    free(samples);
    setStatusColor(64, 0, 0);
    Serial.printf(
        "CAPTURE_DROPPED,file=%s,samples=%lu,reason=too_few_samples\n",
        path,
        (unsigned long)rows);
    delay(1000);
    setStatusColor(0, 0, 32);
    return false;
  }

  File file = LittleFS.open(path, FILE_WRITE);
  if (!file) {
    Serial.printf("CAPTURE_ERROR,open_failed,%s\n", path);
    free(samples);
    return false;
  }

  file.println("seq,timestamp_us,ax_mg,ay_mg,az_mg,gx_dps,gy_dps,gz_dps,temp_c");
  uint32_t writtenRows = 0;
  for (uint32_t index = 0; index < rows; index++) {
    const RawSample &sample = samples[index];
    const size_t written = file.printf(
        "%lu,%lld,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f\n",
        (unsigned long)index,
        (long long)sample.timestampUs,
        sample.ax / 2.048f,
        sample.ay / 2.048f,
        sample.az / 2.048f,
        sample.gx / 16.4f,
        sample.gy / 16.4f,
        sample.gz / 16.4f,
        ((float)sample.temp - 21.0f) / 333.87f + 21.0f);

    if (written == 0) {
      writeFailed = true;
      break;
    }
    writtenRows++;
  }
  file.flush();
  file.close();

  const size_t freeAtEnd = LittleFS.totalBytes() - LittleFS.usedBytes();
  appendTelemetrySample(
      telemetry,
      telemetryRows,
      (uint32_t)((esp_timer_get_time() - startUs) / 1000));
  char telemetryPath[40];
  buildTelemetryPath(path, telemetryPath, sizeof(telemetryPath));
  bool telemetryWriteFailed = false;
  File telemetryFile = LittleFS.open(telemetryPath, FILE_WRITE);
  if (!telemetryFile) {
    telemetryWriteFailed = true;
  } else {
    telemetryFile.println("elapsed_ms,free_bytes");
    for (uint32_t index = 0; index < telemetryRows; index++) {
      const size_t written = telemetryFile.printf(
          "%lu,%lu\n",
          (unsigned long)telemetry[index].elapsedMs,
          (unsigned long)telemetry[index].freeBytes);
      if (written == 0) {
        telemetryWriteFailed = true;
        break;
      }
    }
    telemetryFile.flush();
    telemetryFile.close();
  }
  if (telemetryWriteFailed && LittleFS.exists(telemetryPath)) {
    LittleFS.remove(telemetryPath);
  }
  free(samples);

  const int64_t writeEndUs = esp_timer_get_time();
  const bool noSamples = rows == 0;
  if (writeFailed || noSamples) {
    LittleFS.remove(path);
    if (LittleFS.exists(telemetryPath)) {
      LittleFS.remove(telemetryPath);
    }
    setStatusColor(64, 0, 0);
  } else {
    setStatusColor(0, 64, 0);
  }

  Serial.printf(
      "CAPTURE_DONE,file=%s,samples=%lu,written=%lu,duration_ms=%.1f,"
      "write_ms=%.1f,errors=%lu,resets=%lu,write_failed=%u,no_samples=%u,"
      "no_data_polls=%lu,no_data_reads=%lu,free_before=%lu,free_after=%lu,"
      "telemetry_rows=%lu,telemetry_written=%u\n",
      path,
      (unsigned long)rows,
      (unsigned long)writtenRows,
      (double)(endTimeUs - startUs) / 1000.0,
      (double)(writeEndUs - writeStartUs) / 1000.0,
      (unsigned long)(totalErrors - errorsAtStart),
      (unsigned long)(totalResets - resetsAtStart),
      writeFailed ? 1 : 0,
      noSamples ? 1 : 0,
      (unsigned long)noDataPolls,
      (unsigned long)noDataReads,
      (unsigned long)freeAtStart,
      (unsigned long)freeAtEnd,
      (unsigned long)telemetryRows,
      telemetryWriteFailed ? 0 : 1);

  delay(1000);
  setStatusColor(0, 0, 32);
  return rows > 0 && !writeFailed && writtenRows == rows;
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
        "INFO,filesystem_total=%lu,filesystem_used=%lu,filesystem_free=%lu\n",
        (unsigned long)LittleFS.totalBytes(),
        (unsigned long)LittleFS.usedBytes(),
        (unsigned long)(LittleFS.totalBytes() - LittleFS.usedBytes()));
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

  if (now < captureArmedAtMs) {
    buttonDownSinceMs = 0;
    buttonCaptureLatched = false;
    return false;
  }

  if (!isDown) {
    buttonDownSinceMs = 0;
    buttonCaptureLatched = false;
    return false;
  }

  if (buttonDownSinceMs == 0) {
    buttonDownSinceMs = now;
    return false;
  }

  if (!buttonCaptureLatched && now - buttonDownSinceMs >= BUTTON_HOLD_MS) {
    buttonCaptureLatched = true;
    return true;
  }

  return false;
}

#if ENABLE_BLE_CONTROL
static void setupBleControl() {
  BLEDevice::init(BLE_DEVICE_NAME);
  BLEDevice::setMTU(64);
  BLEServer *server = BLEDevice::createServer();
  server->setCallbacks(new KineShootBleServerCallbacks());

  BLEService *controlService = server->createService(BLE_CONTROL_SERVICE_UUID);
  BLECharacteristic *controlCharacteristic = controlService->createCharacteristic(
      BLE_CONTROL_CHARACTERISTIC_UUID,
      BLECharacteristic::PROPERTY_WRITE | BLECharacteristic::PROPERTY_WRITE_NR |
          BLECharacteristic::PROPERTY_READ);
  controlCharacteristic->setCallbacks(new KineShootBleCommandCallbacks());
  controlService->start();

  BLEAdvertising *advertising = BLEDevice::getAdvertising();
  advertising->addServiceUUID(BLE_CONTROL_SERVICE_UUID);
  advertising->setScanResponse(true);
  advertising->start();
  Serial.printf(
      "BLE_CONTROL_READY,name=%s,service=%s,characteristic=%s\n",
      BLE_DEVICE_NAME,
      BLE_CONTROL_SERVICE_UUID,
      BLE_CONTROL_CHARACTERISTIC_UUID);
}
#endif

void setup() {
  Serial.begin(SERIAL_BAUD);
  delay(1000);
  Serial.println("IMU_FLASH_V4_BOOT");

  pinMode(BOOT_BUTTON_PIN, INPUT_PULLUP);
  buttonDownSinceMs = 0;
  buttonCaptureLatched = false;

  if (!mountFileSystem()) {
    Serial.println("FILESYSTEM_ERROR");
    while (true) {
      delay(1000);
    }
  }

  cleanupInvalidCaptureFiles();

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
    setStatusColor(64, 0, 0);
    Serial.println("IMU_FLASH_V4_FATAL");
    while (true) {
      delay(1000);
    }
  }

  Serial.println("IMU_FLASH_V4_READY");
  Serial.println(
      "Commands: LIST, INFO, START, DUMP /capture_001.csv, "
      "DELETE /capture_001.csv");
#if ENABLE_BLE_CONTROL
  setupBleControl();
#endif
  captureArmedAtMs = millis() + BUTTON_STARTUP_ARM_MS;
  setStatusColor(0, 0, 32);
}

void loop() {
  pollSerialCommands();

  if (consumeButtonPress()) {
    recordCapture();
  }

#if ENABLE_BLE_CONTROL
  if (bleCapturePending) {
    bleCapturePending = false;
    recordCapture();
  }
#endif

  delay(5);
}
