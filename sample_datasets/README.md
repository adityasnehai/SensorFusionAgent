# Sample Datasets

This folder provides two ready-to-upload ZIP files for quick testing:

- `dataset1_sample.zip`
- `dataset2_sample.zip`

Each ZIP contains:

```text
participant_01/
  accelerometer.csv
  gyroscope.csv
```

These samples are small synthetic IMU datasets with:
- timestamp column in ISO format
- accelerometer axes (`acc_x`, `acc_y`, `acc_z`)
- gyroscope axes (`gyro_x`, `gyro_y`, `gyro_z`)
- slight timestamp offset between dataset1 and dataset2 for alignment testing

Use them as `dataset1` and `dataset2` in the upload UI.
