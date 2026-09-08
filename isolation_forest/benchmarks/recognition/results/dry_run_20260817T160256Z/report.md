# AutoFLAME recognition benchmark dry-run

No API calls were made.

| Target | Family | Expected peers | Leakage |
| ---: | --- | --- | --- |
| 1500 | DAQ automatic restart | [1604] | PASS |
| 1604 | DAQ automatic restart | [1500] | PASS |
| 1637 | broken PMT base | [1640, 1642] | PASS |
| 1640 | broken PMT base | [1637, 1642] | PASS |
| 1642 | broken PMT base | [1637, 1640] | PASS |
| 1702 | VMax distribution shift | [1703] | PASS |
| 1703 | VMax distribution shift | [1702] | PASS |
| 2068 | LVDS connection/noise failure | [2126] | PASS |
| 2126 | LVDS connection/noise failure | [2068] | PASS |
