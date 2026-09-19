# Motion Report

`tools/build_motion_report.py` creates an offline HTML report from each capture
CSV. It also writes a derived CSV with world-frame acceleration, estimated
orientation, velocity, and path data. The report interface is in Chinese.

The report contains:

- acceleration and angular-velocity curves
- gravity-removed acceleration and orientation estimates
- a synchronized 2D path with playback controls
- a force-direction arrow for the current sample

Reports are generated on demand. The normal export workflow does not create a
report automatically.

Run it after an export:

```powershell
python tools/build_motion_report.py --latest data --open
```

Position and speed are schematic IMU estimates. They are useful for comparing
movement shape and timing, but they are not calibrated centimetre-level
positioning. Accurate position tracking requires an external reference such as
vision, UWB, or a calibrated motion-capture system.
