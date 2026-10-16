#!/usr/bin/env python3
"""
QUASAR CORE - p2p.py

v1 peer-to-peer networking for the Quasar blockchain. Turns the local
single-node chain into a PUBLIC network: nodes connect over TCP, share
blocks and transactions, and converge on the longest VALID chain
(Bitcoin-style).

Protocol: newline-delimited JSON messages over TCP. Message types:
    hello      - handshake: version, height, tip, genesis, listen port
    getpeers   - "who else is out there?"
    peers      - list of "host:port" peers
    getblocks  - "send me blocks after height X"
    blocks     - batch of blocks (reply to getblocks)
    getblock   - "send me the single block at height X"
    block_reply- single block (reply to getblock)
    block      - broadcast: "I just mined this block"
    tx         - broadcast: "here is a new signed transaction"
    ping/pong  - keepalive

Threading: the server accept-loop, every connection reader, and chain
sync each run in daemon threads. All blockchain access goes through one
RLock so mining and networking never corrupt each other.

v1 LIMITATIONS (honest):
  - No encryption, no authentication: anyone can connect. Do NOT run an
    open node on the public internet yet; keep it on localhost / a VPN
    between friends' machines for now.
  - No Sybil protection: a flood of fake nodes could lie about chain
    height (but they CANNOT forge a longer VALID chain - every block is
    fully re-validated, hashes, PoW and signatures included).
  - Fork choice is "longest valid chain"; ties are not resolved by total
    work yet. Fine while everyone mines on one tip.
  - Sync walks back at most 1000 blocks to find a common ancestor.

EDUCATIONAL NETWORK ONLY. Coins have no monetary value.
"""

import json
import os
import random
import socket
import threading
import time

from node import Blockchain, Block, DEFAULT_DIFFICULTY
from transactions import (Transaction, TxInput, TxOutput,
                          qsr_to_quarks, QUARKS_PER_QSR)
from supply import TARGET_SECONDS_PER_BLOCK
from wallet import Wallet

PROTOCOL_VERSION = 1
DEFAULT_PORT = 9333
MAX_BLOCKS_PER_MSG = 200
MAX_MSG_BYTES = 10 * 1024 * 1024
SYNC_TIMEOUT = 20
MAX_ANCESTOR_WALKBACK = 1000

SEEDS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "seeds.json")


def load_seeds(path: str = SEEDS_PATH) -> list:
    """Read ["host:port", ...] from seeds.json. Empty list if missing."""
    try:
        with open(path) as f:
            return [s for s in json.load(f).get("seeds", []) if s]
    except (OSError, ValueError):
        return []


def _report_mined_block(miner_address: str, res: dict) -> None:
    """Optional website-wallet bridge: POST mined-block stats to QUASAR_REPORT_URL.

    Dormant unless the env var is set (the one-click installer sets it from
    quasar-report.txt next to the installer). Supports two targets:
      - Firestore REST (URL contains firestore.googleapis.com):
        writes a doc into the 'reports' collection (see FIREBASE_SETUP.txt).
      - Anything else: plain JSON POST.
    All errors are swallowed so reporting can never break mining.
    """
    url = os.environ.get("QUASAR_REPORT_URL", "").strip()
    if not url:
        return
    try:
        import urllib.request
        height = int(res.get("height") or 0)
        ts = int(time.time())
        if "firestore.googleapis.com" in url:
            payload = json.dumps({"fields": {
                "miner": {"stringValue": str(miner_address)},
                "height": {"integerValue": str(height)},
                "hash": {"stringValue": str(res.get("hash") or "")},
                "ts": {"integerValue": str(ts)},
            }}).encode()
        else:
            payload = json.dumps({
                "miner": miner_address,
                "height": height,
                "hash": res.get("hash"),
                "ts": ts,
                "source": "quasar-oneclick-miner",
            }).encode()
        req = urllib.request.Request(url, data=payload,
                                     headers={"Content-Type": "application/json"},
                                     method="POST")
        urllib.request.urlopen(req, timeout=8).read()
    except Exception:
        pass


# ================================================================== peer conn
class PeerConn:
    """One TCP connection to a peer. Owns a reader thread."""

    def __init__(self, node, sock: socket.socket, addr, outbound: bool):
        self.node = node
        self.sock = sock
        self.addr = addr              # (host, port) of the socket peer
        self.outbound = outbound
        self.key = None               # (host, listen_port), set after hello
        self.remote_height = 0
        self.remote_tip = None
        self.remote_node_id = ""
        self.alive = True
        self._send_lock = threading.Lock()
        self._pend_lock = threading.Lock()
        self._pending = {}            # msg_type -> (event, box)

    # ------------------------------------------------------------ lifecycle
    def start(self):
        t = threading.Thread(target=self._reader, daemon=True,
                             name=f"p2p-reader-{self.addr}")
        t.start()

    def close(self):
        if not self.alive:
            return
        self.alive = False
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass
        node = self.node
        with node.lock:
            for k, v in list(node.peers.items()):
                if v is self:
                    del node.peers[k]

    # ----------------------------------------------------------------- send
    def send(self, obj: dict) -> bool:
        if not self.alive:
            return False
        try:
            data = (json.dumps(obj, separators=(",", ":")) + "\n"
                    ).encode("utf-8")
            with self._send_lock:
                self.sock.sendall(data)
            return True
        except OSError:
            self.close()
            return False

    def send_hello(self):
        with self.node.lock:
            bc = self.node.bc
            height = len(bc.chain) - 1
            tip = bc.chain[-1].hash
            genesis = bc.chain[0].hash
        self.send({"type": "hello", "version": PROTOCOL_VERSION,
                   "height": height, "tip": tip, "genesis": genesis,
                   "listen_port": self.node.port,
                   "node_id": self.node.node_id})

    def request(self, expect_type: str, payload: dict,
                timeout: int = SYNC_TIMEOUT):
        """Send `payload`, wait for a message of `expect_type`. Returns it."""
        ev = threading.Event()
        box = {}
        with self._pend_lock:
            self._pending[expect_type] = (ev, box)
        try:
            if not self.send(payload):
                return None
            if not ev.wait(timeout):
                return None
            return box.get("msg")
        finally:
            with self._pend_lock:
                self._pending.pop(expect_type, None)

    # ---------------------------------------------------------------- reader
    def _reader(self):
        buf = b""
        try:
            while self.alive and self.node.running:
                try:
                    data = self.sock.recv(65536)
                except OSError:
                    break
                if not data:
                    break
                buf += data
                if len(buf) > MAX_MSG_BYTES + 1024:
                    break  # peer is misbehaving; drop it
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if len(line) > MAX_MSG_BYTES:
                        continue
                    if not line.strip():
                        continue
                    try:
                        msg = json.loads(line.decode("utf-8"))
                    except (ValueError, UnicodeDecodeError):
                        continue
                    if isinstance(msg, dict) and "type" in msg:
                        self.node._dispatch(self, msg)
        finally:
            self.close()


# ================================================================== p2p node
class P2PNode:
    """A networked Quasar node: blockchain + TCP server + peer manager."""

    def __init__(self, port: int = DEFAULT_PORT, blockchain: Blockchain = None,
                 data_path: str = None, seeds: list = None):
        self.port = port
        self.bc = blockchain or Blockchain.load(data_path=data_path)
        self.lock = threading.RLock()
        self.node_id = "%016x" % random.getrandbits(64)
        self.peers = {}               # (host, listen_port) -> PeerConn
        self.seen_txs = set()
        self.seen_blocks = set()
        self.running = False
        self._server_sock = None
        self._syncing = False
        self._sync_lock = threading.Lock()
        self.seeds = seeds if seeds is not None else load_seeds()

    # --------------------------------------------------------------- startup
    def start(self):
        """Start the server socket and connect to seed nodes (non-blocking)."""
        self.running = True
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("0.0.0.0", self.port))
        srv.listen(20)
        srv.settimeout(1.0)
        self._server_sock = srv
        threading.Thread(target=self._accept_loop, daemon=True,
                         name="p2p-accept").start()
        for seed in self.seeds:
            try:
                host, port = seed.rsplit(":", 1)
                self.connect_to(host.strip(), int(port.strip()))
            except ValueError:
                pass
        return self

    def stop(self):
        self.running = False
        try:
            self._server_sock.close()
        except (OSError, AttributeError):
            pass
        with self.lock:
            conns = [c for c in self.peers.values() if c is not None]
        for c in conns:
            c.close()

    def _accept_loop(self):
        while self.running:
            try:
                sock, addr = self._server_sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            conn = PeerConn(self, sock, addr, outbound=False)
            # Temporary key until hello tells us their listen port.
            with self.lock:
                self.peers[("inbound", id(sock))] = conn
            conn.start()
            conn.send_hello()

    # ----------------------------------------------------------------- peers
    def _is_self(self, host: str, port: int) -> bool:
        if int(port) != self.port:
            return False
        if host in ("127.0.0.1", "localhost", "::1"):
            return True
        try:
            if host == socket.gethostname():
                return True
            for fam, _t, _p, _c, sockaddr in socket.getaddrinfo(
                    socket.gethostname(), None):
                if sockaddr[0] == host:
                    return True
        except OSError:
            pass
        return False

    def connect_to(self, host: str, port: int):
        """Open an outbound connection to a peer. Returns (ok, msg)."""
        port = int(port)
        if self._is_self(host, port):
            return False, "that's this node"
        key = (host, port)
        with self.lock:
            if key in self.peers and self.peers[key] is not None:
                return False, "already connected"
            self.peers[key] = None  # placeholder: prevents racing dials
        try:
            sock = socket.create_connection((host, port), timeout=10)
        except OSError as e:
            with self.lock:
                self.peers.pop(key, None)
            return False, f"connection failed: {e}"
        conn = PeerConn(self, sock, (host, port), outbound=True)
        with self.lock:
            self.peers[key] = conn
        conn.key = key
        conn.start()
        conn.send_hello()
        return True, f"connected to {host}:{port}"

    def peer_list(self):
        with self.lock:
            out = []
            for (h, p), c in self.peers.items():
                if c is None:
                    continue
                out.append({"host": h, "port": p,
                            "height": c.remote_height,
                            "outbound": c.outbound})
            return out

    # -------------------------------------------------------------- messaging
    def _relay(self, payload: dict, exclude=None):
        with self.lock:
            conns = [c for c in self.peers.values()
                     if c is not None and c is not exclude and c.alive]
        for c in conns:
            c.send(payload)

    def _seen_add(self, seen: set, h: str):
        seen.add(h)
        if len(seen) > 20000:
            seen.clear()
            seen.add(h)

    def _dispatch(self, conn: PeerConn, msg: dict):
        t = msg.get("type")
        # 1. Fulfil any pending request first (sync path never blocks here).
        with conn._pend_lock:
            if t in conn._pending:
                ev, box = conn._pending.pop(t)
                box["msg"] = msg
                ev.set()
                return
        # 2. Otherwise handle as an unsolicited message.
        handler = {
            "hello": self._on_hello,
            "getpeers": self._on_getpeers,
            "peers": self._on_peers,
            "getblocks": self._on_getblocks,
            "getblock": self._on_getblock,
            "block": self._on_block_broadcast,
            "tx": self._on_tx_broadcast,
            "ping": lambda c, m: c.send({"type": "pong"}),
        }.get(t)
        if handler:
            try:
                handler(conn, msg)
            except Exception:
                pass  # v1: never let a bad message kill the reader

    # --------------------------------------------------------------- handlers
    def _on_hello(self, conn: PeerConn, msg: dict):
        with self.lock:
            our_genesis = self.bc.chain[0].hash
            our_height = len(self.bc.chain) - 1
        if msg.get("genesis") != our_genesis:
            conn.close()  # different network/genesis: not our chain
            return
        conn.remote_height = int(msg.get("height", 0))
        conn.remote_tip = msg.get("tip")
        conn.remote_node_id = str(msg.get("node_id", ""))
        listen_port = msg.get("listen_port")
        if listen_port:
            new_key = (conn.addr[0], int(listen_port))
            with self.lock:
                # Drop our temporary inbound key for this conn.
                for k, v in list(self.peers.items()):
                    if v is conn and k != new_key:
                        del self.peers[k]
                existing = self.peers.get(new_key)
                if existing is not None and existing is not conn:
                    # Duplicate connection: deterministic tie-break.
                    # Higher node_id keeps its OUTBOUND; the lower keeps
                    # the inbound. Both sides converge on one connection.
                    if conn.remote_node_id > self.node_id:
                        existing.close()       # they win: drop ours
                        self.peers[new_key] = conn
                        conn.key = new_key
                    else:
                        conn.close()           # we win: drop the inbound
                        return
                else:
                    self.peers[new_key] = conn
                    conn.key = new_key
        conn.send({"type": "getpeers"})
        if conn.remote_height > our_height:
            threading.Thread(target=self.sync_with_peer, args=(conn,),
                             daemon=True, name="p2p-sync").start()

    def _on_getpeers(self, conn: PeerConn, msg: dict):
        with self.lock:
            peers = [f"{h}:{p}" for (h, p), c in self.peers.items()
                     if c is not None and c.alive and h != "inbound"]
        conn.send({"type": "peers", "peers": peers})

    def _on_peers(self, conn: PeerConn, msg: dict):
        tried = 0
        for p in msg.get("peers", []):
            if tried >= 5:
                break
            try:
                host, port = p.rsplit(":", 1)
                port = int(port)
            except ValueError:
                continue
            if self._is_self(host, port):
                continue
            with self.lock:
                if (host, port) in self.peers:
                    continue
            ok, _ = self.connect_to(host, port)
            if ok:
                tried += 1

    def _on_getblocks(self, conn: PeerConn, msg: dict):
        try:
            frm = int(msg.get("from_height", 0))
        except (TypeError, ValueError):
            return
        with self.lock:
            chunk = [b.to_dict()
                     for b in self.bc.chain[frm + 1: frm + 1 + MAX_BLOCKS_PER_MSG]]
        conn.send({"type": "blocks", "from_height": frm, "blocks": chunk})

    def _on_getblock(self, conn: PeerConn, msg: dict):
        try:
            h = int(msg.get("height", -1))
        except (TypeError, ValueError):
            h = -1
        with self.lock:
            blk = (self.bc.chain[h].to_dict()
                   if 0 <= h < len(self.bc.chain) else None)
        conn.send({"type": "block_reply", "height": h, "block": blk})

    def _on_block_broadcast(self, conn: PeerConn, msg: dict):
        try:
            block = Block.from_dict(msg["block"])
        except (KeyError, TypeError, ValueError):
            return
        relay, need_sync = None, False
        with self.lock:
            if block.hash in self.seen_blocks:
                return
            self._seen_add(self.seen_blocks, block.hash)
            ok, why = self.bc.validate_next_block(block)
            if ok:
                self.bc.append_validated_block(block)
                relay = block
            elif "prev_hash" in why or "height" in why:
                # Valid-looking block we can't attach: we are behind/forked.
                need_sync = (conn.remote_height >= len(self.bc.chain) - 1
                             or True)
        if relay is not None:
            self._relay({"type": "block", "block": relay.to_dict()},
                        exclude=conn)
        elif need_sync:
            threading.Thread(target=self.sync_with_peer, args=(conn,),
                             daemon=True, name="p2p-sync").start()

    def _on_tx_broadcast(self, conn: PeerConn, msg: dict):
        try:
            tx = Transaction.from_dict(msg["tx"])
        except (KeyError, TypeError, ValueError):
            return
        relay = None
        with self.lock:
            if tx.tx_hash() in self.seen_txs:
                return
            self._seen_add(self.seen_txs, tx.tx_hash())
            ok, _ = self.bc.add_transaction(tx)
            if ok:
                self.bc.save()
                relay = tx
        if relay is not None:
            self._relay({"type": "tx", "tx": relay.to_dict()}, exclude=conn)

    # ------------------------------------------------------------------ sync
    def sync_with_peer(self, conn: PeerConn):
        """Download missing blocks from a peer (longest VALID chain wins)."""
        with self._sync_lock:
            if self._syncing:
                return
            self._syncing = True
        try:
            self._do_sync(conn)
        finally:
            with self._sync_lock:
                self._syncing = False

    def _do_sync(self, conn: PeerConn):
        with self.lock:
            our_height = len(self.bc.chain) - 1
        peer_height = conn.remote_height or 0
        if peer_height <= our_height:
            return
        # Phase 1: try a straight extension from our tip.
        while True:
            with self.lock:
                our_height = len(self.bc.chain) - 1
                tip_hash = self.bc.chain[-1].hash
            if our_height >= peer_height:
                return
            resp = conn.request("blocks",
                                {"type": "getblocks", "from_height": our_height})
            if not resp:
                return
            raw = resp.get("blocks", [])
            if not raw:
                return
            try:
                blocks = [Block.from_dict(b) for b in raw]
            except (TypeError, ValueError):
                return
            first = blocks[0]
            if not (first.prev_hash == tip_hash
                    and first.height == our_height + 1):
                self._sync_fork(conn, peer_height)  # not a clean extension
                return
            new_tip = None
            with self.lock:
                for b in blocks:
                    if b.hash in self.seen_blocks:
                        continue
                    ok, _ = self.bc.validate_next_block(b)
                    if not ok:
                        return  # peer sent junk; abort sync
                    self._seen_add(self.seen_blocks, b.hash)
                    self.bc.append_validated_block(b)
                    new_tip = b
            if new_tip is not None:
                self._relay({"type": "block",
                             "block": new_tip.to_dict()}, exclude=conn)

    def _sync_fork(self, conn: PeerConn, peer_height: int):
        """Find our common ancestor with the peer, then adopt their longer
        chain if (and only if) it fully validates."""
        with self.lock:
            our_height = len(self.bc.chain) - 1
        hi = min(our_height, peer_height)
        ancestor = None
        for h in range(hi, max(hi - MAX_ANCESTOR_WALKBACK, -1), -1):
            resp = conn.request("block_reply",
                                {"type": "getblock", "height": h}, timeout=10)
            if not resp or not resp.get("block"):
                continue
            try:
                rb = Block.from_dict(resp["block"])
            except (TypeError, ValueError):
                continue
            with self.lock:
                if h < len(self.bc.chain) and self.bc.chain[h].hash == rb.hash:
                    ancestor = h
                    break
        if ancestor is None:
            return  # no common ancestor in walkback range: give up
        # Download everything after the ancestor.
        new_blocks = []
        frm = ancestor
        while True:
            resp = conn.request("blocks",
                                {"type": "getblocks", "from_height": frm})
            if not resp or not resp.get("blocks"):
                break
            try:
                chunk = [Block.from_dict(b) for b in resp["blocks"]]
            except (TypeError, ValueError):
                return
            new_blocks.extend(chunk)
            frm = chunk[-1].height
            if len(chunk) < MAX_BLOCKS_PER_MSG or frm >= peer_height:
                break
        if not new_blocks:
            return
        adopted_tip = None
        with self.lock:
            if new_blocks[0].prev_hash != self.bc.chain[ancestor].hash:
                return
            candidate = self.bc.chain[:ancestor + 1] + new_blocks
            ok, msg = self.bc.adopt_chain(candidate)
            if ok:
                adopted_tip = self.bc.chain[-1]
                print(f"[p2p] {msg}", flush=True)
        if adopted_tip is not None:
            self._relay({"type": "block",
                         "block": adopted_tip.to_dict()}, exclude=conn)

    # ------------------------------------------------------- local actions
    def mine_and_broadcast(self, miner_address: str) -> dict:
        """Mine one block locally, then broadcast it to all peers."""
        with self.lock:
            res = self.bc.mine_pending(miner_address)
            if not res.get("ok"):
                return res
            block = self.bc.chain[-1]
            self._seen_add(self.seen_blocks, block.hash)
            payload = {"type": "block", "block": block.to_dict()}
        self._relay(payload)
        return res

    def mine_auto_and_broadcast(self, miner_address: str, count: int = None,
                                pace_seconds: float = TARGET_SECONDS_PER_BLOCK
                                ) -> dict:
        """Auto-mine with pacing, broadcasting each block to peers.

        Miner policy only (no consensus change): blocks are paced
        ~pace_seconds apart (default 30s) via Blockchain.mine_auto, so the
        retarget sees the block time it expects and difficulty stays
        stable instead of ratcheting up. The node lock is held only while
        a block is being mined (never during the wait), so P2P sync keeps
        working between blocks. Ctrl+C stops cleanly at any point — a
        half-mined block is never appended or broadcast.
        """
        counts = {"n": 0}

        def _broadcast(res):
            with self.lock:
                block = self.bc.chain[-1]
                self._seen_add(self.seen_blocks, block.hash)
                payload = {"type": "block", "block": block.to_dict()}
            self._relay(payload)
            counts["n"] += 1
            print(f"  auto-mined block {res['height']} "
                  f"{res['hash'][:16]}... broadcast to "
                  f"{len(self.peer_list())} peer(s) "
                  f"[session total: {counts['n']}]", flush=True)
            _report_mined_block(miner_address, res)

        def _wait(secs):
            print(f"  next block in ~{secs:.0f}s "
                  f"(Ctrl+C stops auto-mine)...", flush=True)

        return self.bc.mine_auto(miner_address, count=count,
                                 pace_seconds=pace_seconds,
                                 on_block=_broadcast, on_wait=_wait,
                                 lock=self.lock)

    def submit_tx(self, tx: Transaction):
        """Validate + mempool a local tx, then broadcast it."""
        with self.lock:
            if tx.tx_hash() in self.seen_txs:
                return False, "already seen"
            ok, msg = self.bc.add_transaction(tx)
            if ok:
                self.bc.save()
                self._seen_add(self.seen_txs, tx.tx_hash())
        if ok:
            self._relay({"type": "tx", "tx": tx.to_dict()})
        return ok, msg

    def build_send_tx(self, wallet: Wallet, to_addr: str,
                      amount_quarks: int) -> Transaction:
        """Build + sign a tx spending `wallet`'s UTXOs (unsigned change back)."""
        if amount_quarks <= 0:
            raise ValueError("amount must be positive")
        with self.lock:
            owned = [(k, v) for k, v in self.bc.utxo.items()
                     if v[0] == wallet.address]
        owned.sort(key=lambda kv: kv[1][1])
        chosen, total = [], 0
        for key, (_addr, amt) in owned:
            chosen.append(key)
            total += amt
            if total >= amount_quarks:
                break
        if total < amount_quarks:
            raise ValueError(
                f"insufficient funds: have {total / QUARKS_PER_QSR:.8f} QSR")
        inputs = [TxInput(h, idx) for (h, idx) in chosen]
        outputs = [TxOutput(to_addr, amount_quarks)]
        if total > amount_quarks:
            outputs.append(TxOutput(wallet.address, total - amount_quarks))
        tx = Transaction(inputs, outputs)
        for i in range(len(inputs)):
            tx.sign_input(i, wallet)
        return tx


# ================================================================== console
def _resolve(console_bc_owner, name_or_addr: str) -> str:
    if name_or_addr.startswith("Q"):
        return name_or_addr
    return Wallet.load(name_or_addr).address


def _do_mine_auto(node: P2PNode, args: list) -> None:
    """Run 'mine-auto <wallet> [count]'. Shared by the console command
    and the --mine-auto autostart flag (one-click installer)."""
    if not (1 <= len(args) <= 2):
        print("  usage: mine-auto <wallet> [count]")
        return
    count = None
    if len(args) == 2:
        try:
            count = int(args[1])
        except ValueError:
            print("  count must be a whole number")
            return
        if count <= 0:
            print("  count must be positive")
            return
    addr = _resolve(node, args[0])
    print(f"  auto-mining to {addr}: one block every "
          f"{TARGET_SECONDS_PER_BLOCK:.0f}s. Ctrl+C stops.")
    res = node.mine_auto_and_broadcast(addr, count=count)
    if res.get("ok"):
        print(f"  auto-mine stopped: {res['mined']} block(s) "
              f"mined this session")
    else:
        print(f"  auto-mine stopped: {res['mined']} block(s) "
              f"mined, then: {res.get('error')}")


def run_console(node: P2PNode, autostart_wallet: str = ""):
    """Interactive console: mining/CLI keep working while P2P runs behind."""
    print(f"\nQuasar P2P node on port {node.port} "
          f"(peers: {len(node.peer_list())}). Type 'help'. Ctrl+C quits.\n")
    if autostart_wallet:
        print(f"  --mine-auto: starting automatic mining "
              f"to '{autostart_wallet}' ...\n")
        try:
            _do_mine_auto(node, [autostart_wallet])
        except (EOFError, KeyboardInterrupt):
            print("\n  auto-mine stopped by user.")
        except Exception as e:  # e.g. wallet not created yet
            print(f"\n  auto-mine could not start: {e}")
            print(f"  create the wallet first: "
                  f"python quasar_cli.py new-address {autostart_wallet}")
        print("\n  Node is still running. Type 'help' for commands, "
              "'quit' to stop.\n")
    while True:
        try:
            line = input(f"quasar-node:{node.port}> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nStopping node...")
            break
        if not line:
            continue
        parts = line.split()
        cmd, args = parts[0], parts[1:]
        try:
            if cmd in ("quit", "exit"):
                break
            elif cmd == "help":
                print("  info | mine <wallet> | mine-auto <wallet> [count] |\n"
                      "  send <from> <to> <qsr> | balance <wallet|addr>\n"
                      "  claim-founder <amount_qsr> | mempool | validate | "
                      "peers | add-peer <host:port> | quit\n"
                      "  mine-auto: mines continuously, one block every "
                      f"{TARGET_SECONDS_PER_BLOCK:.0f}s (Ctrl+C stops). "
                      "Give [count] to mine exactly that many blocks.")
            elif cmd == "info":
                i = node.bc.info()
                print(f"  height={i['height']} tip={i['tip_hash'][:16]}... "
                      f"mined={i['mined_qsr']:,.2f} mempool={i['mempool_txs']} "
                      f"peers={len(node.peer_list())}")
            elif cmd == "mine" and len(args) == 1:
                addr = _resolve(node, args[0])
                res = node.mine_and_broadcast(addr)
                if res.get("ok"):
                    print(f"  mined block {res['height']} {res['hash'][:16]}... "
                          f"broadcast to {len(node.peer_list())} peer(s)")
                else:
                    print("  mining failed:", res.get("error"))
            elif cmd == "mine-auto" and 1 <= len(args) <= 2:
                _do_mine_auto(node, args)
            elif cmd == "send" and len(args) == 3:
                wallet = Wallet.load(args[0])
                tx = node.build_send_tx(
                    wallet, args[1], qsr_to_quarks(float(args[2])))
                ok, msg = node.submit_tx(tx)
                print(("  broadcast: " if ok else "  rejected: ") + msg)
            elif cmd == "balance" and len(args) == 1:
                addr = _resolve(node, args[0])
                print(f"  {node.bc.get_balance(addr):,.8f} QSR")
            elif cmd == "claim-founder" and len(args) == 1:
                import random
                from transactions import FounderClaimTransaction
                founder = node.bc.founder_address
                if not founder:
                    print("  this chain has no founder address set")
                    continue
                try:
                    amt = qsr_to_quarks(float(args[0]))
                except ValueError:
                    print("  amount must be a number")
                    continue
                if amt <= 0:
                    print("  amount must be positive")
                    continue
                tx = FounderClaimTransaction(
                    founder, amt, random.getrandbits(63))
                ok, msg = node.submit_tx(tx)
                print(("  broadcast: " if ok else "  rejected: ") + msg)
            elif cmd == "mempool":
                print(f"  {len(node.bc.mempool)} pending tx(s)")
            elif cmd == "validate":
                print("  " + node.bc.validate_chain()[1])
            elif cmd == "peers":
                pls = node.peer_list()
                print(f"  {len(pls)} peer(s):")
                for p in pls:
                    print(f"    {p['host']}:{p['port']} "
                          f"height={p['height']} "
                          f"({'out' if p['outbound'] else 'in'})")
            elif cmd == "add-peer" and len(args) == 1:
                host, port = args[0].rsplit(":", 1)
                print("  " + node.connect_to(host, int(port))[1])
            else:
                print("  unknown command - 'help' for list")
        except FileNotFoundError as e:
            print(f"  error: {e}")
        except Exception as e:  # noqa: BLE001 - console must not die
            print(f"  error: {e}")


def start_node(port: int = DEFAULT_PORT, seeds: list = None,
               founder_address: str = "", mine_auto_wallet: str = ""):
    """Start a P2P node and drop into the interactive console.

    founder_address is written into the genesis block ONLY when
    starting a fresh chain (no chain_data.json yet). Peers inherit it
    by syncing genesis from the seed.

    mine_auto_wallet: if given, mining starts automatically to that
    wallet (one-click installer) instead of waiting for a command.
    """
    bc = Blockchain.load(founder_address=founder_address)
    node = P2PNode(port=port, blockchain=bc, seeds=seeds)
    node.start()
    print(f"[p2p] listening on port {port}, node id {node.node_id}")
    print(f"[p2p] seeds: {node.seeds or '(none)'}")
    try:
        run_console(node, autostart_wallet=mine_auto_wallet)
    finally:
        node.stop()
        print("[p2p] node stopped.")
