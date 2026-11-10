#!/usr/bin/env python3
"""Serves Tidebound Corridor on your network and introduces two players for The Rival Stage.

Run:   python3 serve.py            (port 8765)       or   python3 serve.py 9000

It does two things:
  1. serves the game files, exactly like `python3 -m http.server`;
  2. keeps a small list of waiting matches, so a host can share a 5-character room code
     instead of a long one. It only passes the first "hello" between the two games: the
     match itself goes directly between the two devices, encrypted.

Only devices on your own network (private or loopback addresses) are answered by the
matchmaking part. Rooms last five minutes and can be joined once.
"""
import http.server, ipaddress, json, os, secrets, socketserver, sys, threading, time
from urllib.parse import urlparse, parse_qs

ALPHABET = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'   # no 0/O, 1/I/L
TTL = 300                                       # seconds a room lives
MAXLEN = 24000                                  # longest message accepted
ROOMS, FAILS, LOCK = {}, {}, threading.Lock()


def local_only(addr):
    try:
        ip = ipaddress.ip_address(addr.split('%')[0])
        if ip.version == 6 and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        return ip.is_private or ip.is_loopback or ip.is_link_local
    except ValueError:
        return False


def sweep():
    now = time.time()
    for k in [k for k, r in ROOMS.items() if r['exp'] < now]:
        del ROOMS[k]


def too_many_misses(ip):
    now = time.time()
    hits = [t for t in FAILS.get(ip, []) if now - t < 60]
    FAILS[ip] = hits
    return len(hits) >= 12


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        if '/duet/' not in (args[0] if args else ''):
            super().log_message(fmt, *args)

    def reply(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def duet(self, method):
        ip = self.client_address[0]
        if not local_only(ip):
            return self.reply(403, {'error': 'The Rival Stage only works on your own network.'})
        u = urlparse(self.path)
        route, q = u.path[len('/duet/'):], parse_qs(u.query)
        body = {}
        if method == 'POST':
            n = int(self.headers.get('Content-Length') or 0)
            if n > MAXLEN + 200:
                return self.reply(413, {'error': 'Too large.'})
            try:
                body = json.loads(self.rfile.read(n) or b'{}')
            except ValueError:
                return self.reply(400, {'error': 'Bad request.'})
        get = lambda d, k: d.get(k) if isinstance(d.get(k), str) else ''
        room = (q.get('room', [''])[0] if method == 'GET' else get(body, 'room')).upper()
        with LOCK:
            sweep()
            if route == 'ping':
                return self.reply(200, {'ok': 1})
            if route == 'host' and method == 'POST':
                offer = get(body, 'offer')
                if not offer.startswith('TBD1-') or len(offer) > MAXLEN:
                    return self.reply(400, {'error': 'That is not a match code.'})
                if len(ROOMS) > 200:
                    return self.reply(429, {'error': 'Too many matches waiting.'})
                code = ''.join(secrets.choice(ALPHABET) for _ in range(5))
                while code in ROOMS:
                    code = ''.join(secrets.choice(ALPHABET) for _ in range(5))
                ROOMS[code] = {'offer': offer, 'answer': '', 'claimed': False, 'exp': time.time() + TTL}
                return self.reply(200, {'room': code, 'ttl': TTL})
            if route == 'join' and method == 'GET':
                if too_many_misses(ip):
                    return self.reply(429, {'error': 'Too many tries. Wait a minute.'})
                r = ROOMS.get(room)
                if not r or r['claimed']:
                    FAILS.setdefault(ip, []).append(time.time())
                    return self.reply(404, {'error': 'No waiting match has that code. Check it and try again.'})
                r['claimed'] = True
                r['exp'] = time.time() + TTL
                return self.reply(200, {'offer': r['offer']})
            if route == 'answer' and method == 'POST':
                answer, r = get(body, 'answer'), ROOMS.get(room)
                if not r or not r['claimed'] or r['answer'] or not answer.startswith('TBD1-') or len(answer) > MAXLEN:
                    return self.reply(400, {'error': 'That match is no longer open.'})
                r['answer'] = answer
                return self.reply(200, {'ok': 1})
            if route == 'poll' and method == 'GET':
                r = ROOMS.get(room)
                if not r:
                    return self.reply(404, {'error': 'The code expired.'})
                if r['answer']:
                    ans = r['answer']
                    del ROOMS[room]          # the room is used up the moment the host collects the reply
                    return self.reply(200, {'answer': ans})
                return self.reply(200, {'answer': ''})
            if route == 'close' and method == 'POST':
                ROOMS.pop(room, None)
                return self.reply(200, {'ok': 1})
        return self.reply(404, {'error': 'Not found.'})

    def do_GET(self):
        return self.duet('GET') if self.path.startswith('/duet/') else super().do_GET()

    def do_POST(self):
        return self.duet('POST') if self.path.startswith('/duet/') else self.send_error(405)


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(('10.255.255.255', 1)); lan = s.getsockname()[0]; s.close()
    except OSError:
        lan = None
    print(f'Tidebound Corridor is being served.\n  On this computer:   http://localhost:{port}/tidebound-corridor.html')
    if lan:
        print(f'  For other devices:  http://{lan}:{port}/tidebound-corridor.html   (same Wi-Fi or network)')
    print('The Rival Stage short codes are on. Press Ctrl+C to stop.')
    try:
        Server(('0.0.0.0', port), Handler).serve_forever()
    except KeyboardInterrupt:
        pass
