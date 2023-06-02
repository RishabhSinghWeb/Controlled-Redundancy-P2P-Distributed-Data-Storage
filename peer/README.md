How to run?
python peer.py 9000

where 9000 is port number


How beacons find each other?
1. all seeds and peers of beacon.torrent are considered as beacons
2. collection file contains beacon's addresses
3. ask known beacons for more beacons


How beacons connect?
UDP


How data is stored?
No database is required, no database is used.


Long term plan?
Longest active beacons are most stable beacons, ideally these beacons store critical/rare/small files
while newly active beacons will handle more of the bandwidth load.