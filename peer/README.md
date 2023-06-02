#### How to run?
> python peer.py 9000

Where 9000 is port number

#### What is peer?
It sits on top of existing torrent network to provide controlled redundancy. It maintains every torrent's availability **efficiently**.

<sub>We combined beacon and peer into peer.py. So, now they are the same thing that does all the work</sub>


#### How beacons find each other?
1. All seeds and peers of beacon.torrent are considered as beacons
2. Collection file contains beacon's addresses
3. Ask known beacons for more beacons


#### How beacons connect?
UDP


#### How data is stored?
No database is required, no database is used.


#### Long term plan?
Longest active beacons are most stable beacons, ideally these beacons store critical/rare/small files
while newly active beacons will handle more of the bandwidth load.
