#include "ICM_20948.h"
#include <esp_timer.h>

#define I2C_SDA_PIN 8
#define I2C_SCL_PIN 9
#define AD0_VAL 0
#define I2C_CLOCK_HZ 50000UL
#define SERIAL_BAUD 230400

#define MAX_CONSECUTIVE_FAULTS 5
#define STATUS_INTERVAL_MS 1000

ICM_20948_I2C myICM;

uint32_t sequenceNumber = 0;
uint32_t totalSamples = 0;
uint32_t totalErrors = 0;
uint32_t totalResets = 0;
uint16_t consecutiveFaults = 0;
uint32_t lastStatusMs = 0;
int64_t bootTimeUs = 0;

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

static void reportStatus(int64_t nowUs) {
  if ((uint32_t)(millis() - lastStatusMs) < STATUS_INTERVAL_MS) {
    return;
  }

  lastStatusMs = millis();
  const double elapsedSeconds =
      (double)(nowUs - bootTimeUs) / 1000000.0;
  const double sampleRate =
      elapsedSeconds > 0.0 ? (double)totalSamples / elapsedSeconds : 0.0;

  Serial.printf(
      "STAT,hz=%.1f,total=%lu,seq=%lu,errors=%lu,resets=%lu\n",
      sampleRate,
      (unsigned long)totalSamples,
      (unsigned long)sequenceNumber,
      (unsigned long)totalErrors,
      (unsigned long)totalResets);
}

static void readAndPrintSample() {
  uint8_t raw[14];
  const int64_t timestampUs = esp_timer_get_time();
  const ICM_20948_Status_e status =
      myICM.read((uint8_t)AGB0_REG_ACCEL_XOUT_H, raw, sizeof(raw));

  if (status != ICM_20948_Stat_Ok) {
    reportFault(status, timestampUs);
    return;
  }

  consecutiveFaults = 0;

  const int16_t rawAx = be16(&raw[0]);
  const int16_t rawAy = be16(&raw[2]);
  const int16_t rawAz = be16(&raw[4]);
  const int16_t rawGx = be16(&raw[6]);
  const int16_t rawGy = be16(&raw[8]);
  const int16_t rawGz = be16(&raw[10]);
  const int16_t rawTemp = be16(&raw[12]);

  const float axMg = rawAx / 2.048f;
  const float ayMg = rawAy / 2.048f;
  const float azMg = rawAz / 2.048f;
  const float gxDps = rawGx / 16.4f;
  const float gyDps = rawGy / 16.4f;
  const float gzDps = rawGz / 16.4f;
  const float tempC = ((float)rawTemp - 21.0f) / 333.87f + 21.0f;

  Serial.printf(
      "DATA,%lu,%lld,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f\n",
      (unsigned long)sequenceNumber++,
      (long long)timestampUs,
      axMg,
      ayMg,
      azMg,
      gxDps,
      gyDps,
      gzDps,
      tempC);

  totalSamples++;
}

void setup() {
  Serial.begin(SERIAL_BAUD);
  delay(1000);
  Serial.println("IMU_V2_BOOT");

  uint8_t attempts = 0;
  while (!initializeImu() && attempts < 5) {
    attempts++;
    Serial.printf("IMU_INIT_RETRY,attempt=%u\n", attempts);
    delay(500);
  }

  if (myICM.status != ICM_20948_Stat_Ok) {
    Serial.println("IMU_V2_FATAL");
    while (true) {
      delay(1000);
    }
  }

  bootTimeUs = esp_timer_get_time();
  lastStatusMs = millis();

  Serial.println("IMU_V2_READY");
  Serial.println(
      "seq,timestamp_us,ax_mg,ay_mg,az_mg,"
      "gx_dps,gy_dps,gz_dps,temp_c");
}

void loop() {
  if (!myICM.dataReady()) {
    const ICM_20948_Status_e readyStatus = myICM.status;
    if (readyStatus != ICM_20948_Stat_Ok &&
        readyStatus != ICM_20948_Stat_NoData) {
      reportFault(readyStatus, esp_timer_get_time());
    }
    delay(1);
    return;
  }

  readAndPrintSample();
  reportStatus(esp_timer_get_time());
}
