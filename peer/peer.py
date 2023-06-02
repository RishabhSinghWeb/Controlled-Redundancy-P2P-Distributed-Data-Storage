import socket, json, time, select, sys, uuid, hashlib, bencoding, binascii, random, os, platform, subprocess, psutil, cpuinfo  # ,netifaces
from qbittorrent import Client
from io import BytesIO

try:
    with open('config.json') as f:
        config = json.loads(config.read())
except:
    config = {}
DIR = config.get('working_dir', "D:/collection_files/")
collection_files = config.get('collection_files', ["wikipedia.collection", "discord.collection"])
qbittorrent_link = config.get('qbittorrent_link', "http://127.0.0.1:5555/")
peers = config.get('qbittorrent_link', [{'type':'beacon', 'id':None, 'port':9002, 'time':now, 'host':host}])

try:
    qb = Client(qbittorrent_link)
except:
    print("Error: can't connect to qbittorrent app")
    exit()
torrents = {}  # torrents for each collection, like collection_id: [(torrent_file_name, download_status, infohash)]
hashes = {}
targets = {}

for collection in collection_files:
    path = DIR+collection
    paths = []
    try:
        with open(path, "r") as f:
            j = json.loads(f.read())
            torrent_files = []
            for torrent_file_name in j['torrents']:
                try:
                    with open(DIR+torrent_file_name, "rb") as f:
                        data = bencoding.bdecode(f.read())
                    infohash = hashlib.sha1(bencoding.bencode(data[b'info'])).hexdigest()
                    hashes[torrent_file_name] = infohash
                    torrent_files.append((torrent_file_name,False,infohash))  
                except:
                    infohash = None
                    print("Error can't get hash of", torrent_file_name)
            torrents[j['id']] = torrent_files
    except:
        print("can't open", path)

print('torrents:',torrents)
stats = {}


class Torrent:

    def download(torrent):
        qb.download_from_file(open(DIR+torrent, "rb"), savepath=DIR)

    def delete(path, delete_files = False):
        qb.delete(hashes[path])



WEBSITE_PORT = 9000
PEER_OFFLINE_TIME = 60
FLOOD_TIMER = PEER_OFFLINE_TIME*2-2 #28 # not 30 because 30*2=60 by that time peers already assume us offline
CONCENSUS_INTERVAL = 600
SYNC_INTERVAL = 50

now = int(time.time())
consensus_timer = now - (CONCENSUS_INTERVAL - 5) # 5 sec delayed startup
last_sync_time = now - SYNC_INTERVAL + 5 # 5 sec delayed startup waiting for peers to connect
last_flood_time = 0


# starting sockets
host = '0.0.0.0'
try:
    port = int(sys.argv[1])
    WEBSITE_PORT = port+1
except:
    port = 9000



sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((host, port))
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock2 = socket.socket()
inputs = [sock]
print ('Listening on udp %s:%s' % (host, port))

try:
    sock2.bind((host, WEBSITE_PORT))
    sock2.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock2.listen(5)
    inputs.append(sock2)
except:
    print (f"WEBSITE_PORT:{WEBSITE_PORT} is not available")
    

name = f'{str(port)} here!'

while True:
    now = int(time.time())
    for peer in peers:
        if now - peer['time'] > PEER_OFFLINE_TIME: # remove those who have not sent FLOOD messages
            peers.remove(peer)
        elif peer['host'] == host and peer['port'] == port: # remove self from peer list
            peers.remove(peer)

    # getting beacon stats
    if now - last_sync_time > SYNC_INTERVAL:
        for peer in peers:
            try:
                addr_req = (peer['host'], peer['port'])
                sock.sendto(json.dumps({
                        "type": "STATS"
                    }).encode(), addr_req)
            except:
                print("Unable to reach peer: ", peer)
        last_sync_time = now



    # Flood messages on Regular interval
    if now - last_flood_time > FLOOD_TIMER: 
        # # update own data before flood
        for torrent in qb.torrents():
            if torrent['state'] == "pausedUP" or torrent['state'] == "forcedUP" :
                for collection in torrents:
                    for t in torrents[collection]:
                        if t[2] == torrent['hash']:
                            tt = (t[0], True, t[2])
                            torrents[collection].remove(t)
                            torrents[collection].append(tt)

        for collection in targets:
            Torrent.download(targets[collection][0])

        # flood all peers
        for peer in peers: # sent to all peers
            try:
                sock.sendto(json.dumps({
                    'type': 'FLOOD',
                    'host': host,
                    'port': port,
                    'id': str(uuid.uuid4()),
                    'name': name
                    }).encode(), (peer['host'],peer['port']))
            except:
                print("Unable to reach peer: ", peer)
        last_flood_time = now

    # Setting the target
    t_stats = {}
    for addr in stats:
        s = stats[addr]
        for t_id in s:
            if t_id in t_stats:
                t_stats[t_id] = s[t_id] + t_stats[t_id].copy()
            else:
                t_stats[t_id] = s[t_id]
    c_stats = {}
    for t_id in t_stats:
        counter = {}
        x= t_stats[t_id]
        for name,status,infohash in x:
            if name not in counter:
                counter[name] = 0
            if status:
                counter[name] += 1
        c_stats[t_id] = counter

    
    targets = {}
    for c_stat in c_stats:
        sorted_stats = sorted(c_stats[c_stat].items(), key=lambda x:x[1])
        if sorted_stats[0][1] > 3:
            continue

        targets[c_stat] = sorted_stats[0]

    # handling socket request
    read_sockets, write_sockets, error_sockets = select.select( inputs, inputs, [], 5)
    for client in read_sockets:
        # browser request
        if client.getsockname()[1] == WEBSITE_PORT:
            if client is sock2:  # New Connection
                clientsock, clientaddr = client.accept()
                inputs.append(clientsock)
            else:  # Existing Connection
                data = client.recv(1024)
                url = data.decode()[4:].split(" ")[0]
                if url == "/":
                    peers_table = "<thead><td>Who<td>Where<td>last_ping</thead>"
                    for peer in peers:
                        peers_table += f"""<tr><td>{peer['id']}</td><td>{peer['host']}:{peer['port']}</td>
                                            <td>{int(now-peer['time'])} seconds ago</td></tr>"""
                    collection_table = "<thead><td>Messages<td>Torrents<td>Hash</thead>"
                    all_stats = "<h2>Stats</h2>"
                    for addr in stats:
                        stats_table = "<thead><td>Messages<td>Torrents<td>Hash</thead>"
                        stat = stats[addr]
                        for id in stat:
                            s = stat[id]
                            stats_table += f"<tr><td>{id}</td><td>{s}</td><tr>"
                        all_stats += f'<h4>{addr}</h4><table border="1">{stats_table}</table>'
                    # send HTTP response to the browser
                    client.send(f"""HTTP/1.1 200 OK\nContent-Type: html\n\r\n\r\n
                            <head><meta http-equiv="refresh" content="3"></head>
                            <body>
                            <h1>Beacon Status</h1>
                            hosted on: {host}:{port}
                            <h2>Current peers</h2>
                            <table border="1">{peers_table}</table>
                            <h2>torrents to download</h2>
                            {targets}
                            <h3>Currently downloading</h3>{"downloading_queue"}
                            <h3>Downloading Overflow</h3>
                            <h2>The Collection</h2>
                            <table border="1">{collection_table}</table>
                            {all_stats}
                            <h4>Stats Counter</h4>{c_stats}
                            <style>table{{border-collapse:collapse}}thead{{text-align:center;font-weight: bold;}}</style>
                        """.encode())
                    client.close()
                    inputs.remove(client)
                else:
                    st=[]
                    for addr in stats:
                        stat = stats[addr]
                        host,port = addr
                        st.append({'host':host,'port':port,'stat':stat})

                    kb = float(1024)
                    mb = float(kb ** 2)
                    gb = float(kb ** 3)

                    m = psutil.virtual_memory()
                    memTotal = int(m[0]/gb)
                    memFree = int(m[1]/gb)
                    memUsed = int(m[3]/gb)
                    memPercent = int(memUsed/memTotal*100)
                    core = os.cpu_count()
                    CPU_percent = psutil.cpu_percent(0.05)
                    speed = psutil.net_io_counters(pernic=False)
                    psend = round(speed[2]/kb, 2)
                    precv = round(speed[3]/kb, 2)
                    client.send((f"HTTP/1.1 200 OK\nContent-Type: application/json\nAccess-Control-Allow-Origin: *\n\r\n\r\n"+json.dumps({
                            'targets':targets,
                            'host':host,
                            'port':port,
                            'c_stats':c_stats,
                            'stats':st,
                            'peers':peers,
                            'collection_files': collection_files,
                            "CPU_core":core,
                            "memory":   memTotal,
                            "CPU_percent": CPU_percent,
                            "RAM_used": memUsed,
                            "RAM_total": memTotal,
                            "RAM_percent": memPercent,
                            "sent" : speed[0],
                            "packet_send"      : psend,
                            "packet_receive"   : precv,
                            'torrents':qb.torrents(),
                            'c_stats':c_stats,
                            'collection_files': collection_files,
                            'comments': None,
                            'messages': None
                        })).encode())
                    client.close()
                    inputs.remove(client)


        # udp beacon/peer request
        else:
            try:
                data, addr = client.recvfrom(5*1024)
            except:
                continue
            print ('recv %r - %r\n\n' % addr, data)
            req = json.loads(data.decode())

            if req['type'] == 'FLOOD':
                addr_req = (str(req['host'])), int(req['port'])
                for peer in peers:
                    # #print("peer",peer)
                    if peer['host'] == req['host'] and peer['port'] == peer['port']: # old peer
                        peer['time'] = time.time()  # update time for clean up timeout
                        break
                else:  # new peer
                    peers.append({
                        'id': req['id'],
                        'port': int(req['port']),
                        'time': now,
                        'host': str(req['host']),
                        'name': req['name']
                        })

                try:
                    for peer in peers:
                        client.sendto(data, (peer.host, peer.port))
                except:
                    pass

                client.sendto(json.dumps({
                    'type': 'FLOOD_REPLY',
                    'host': host,
                    'port': port,
                    'name': name
                    }).encode(), addr_req) # not replied to sender i.e. addr


            elif req['type'] == 'STATS':
                client.sendto(json.dumps({
                    "type": "STATS_REPLY",
                    "data": torrents
                    }).encode(),addr)

            elif req['type'] == 'STATS_REPLY':
                stats[addr] = req['data']
                for stat in stats:
                    if stat['addr'] == addr and stat['height'] == req['height'] and stat['hash'] == req['hash']:
                        stat[time] = now
                        break
                else:
                    req.pop('type')
                    req['addr'] = addr
                    req['time'] = now
                    stats.append(req)

            elif req['type'] == 'GET_BLOCK':
                try:
                    client.sendto(blockcollection.Blockcollection[req['height']].json().encode(),addr)
                except:
                    client.sendto(json.dumps({
                            'hash':None,
                            'messages': None,
                            'timestamp': None,
                            'type': 'GET_BLOCK_REPLY'
                        }).encode(),addr)

            elif req['type'] == 'GET_BLOCK_REPLY':
                block = Block(req)
                if block.hash:
                    if blockcollection.append(block):
                        pass
                    else:
                        Blockcollection_buffer.append({'block':block, 'time':now})

