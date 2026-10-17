/* Quasar Coin — one-click WEB miner (no download, no upload).
   Press START → mining runs in background Web Workers (same scrypt puzzle
   style as the laptop miner, lighter "web" parameters). Press STOP anytime.
   Progress is saved on your account (Firestore users/{uid}.webMined). */
(function () {
  "use strict";
  var SCRYPT_URL = "https://cdn.jsdelivr.net/npm/scrypt-js@3.0.1/scrypt.js";
  var P = { N: 1 << 14, r: 8, p: 1, bits: 7, tag: "quasar-web" }; // 16 MiB / hash, ~128 tries per block

  var WORKER = "importScripts('" + SCRYPT_URL + "');" +
    "var enc=new TextEncoder(),stop=false;" +
    "function ok(b,n){for(var i=0;i<n;i++){if(b[i>>3]&(0x80>>(i&7)))return false}return true}" +
    "function hex(b){var s='';for(var i=0;i<b.length;i++)s+=('0'+b[i].toString(16)).slice(-2);return s}" +
    "onmessage=function(e){var m=e.data;if(m.type==='stop'){stop=true;return}" +
    "stop=false;var cb=enc.encode(m.challenge),nonce=m.start,duty=m.duty;" +
    "(function loop(){var t=Date.now(),n=0;" +
    "while(!stop&&Date.now()-t<250){var pw=new Uint8Array(cb.length+8);pw.set(cb);" +
    "var dv=new DataView(pw.buffer);dv.setUint32(cb.length,Math.floor(nonce/4294967296));dv.setUint32(cb.length+4,nonce>>>0);" +
    "var pr=scrypt.syncScrypt(pw,cb,m.N,m.r,m.p,32);n++;" +
    "if(ok(pr,m.bits)){postMessage({type:'found',nonce:nonce,proof:hex(pr)});stop=true;return}" +
    "nonce+=m.step}" +
    "if(stop)return;postMessage({type:'rate',n:n,ms:Date.now()-t});" +
    "setTimeout(loop,duty<1?(Date.now()-t)*(1/duty-1):0)})()};";

  var MODES = {
    light:    { label: "Light (1 thread, easy on laptop)", threads: function () { return 1; }, duty: 0.5 },
    balanced: { label: "Balanced (half your CPU)", threads: function (c) { return Math.max(1, c >> 1); }, duty: 1 },
    max:      { label: "Max (all but one core)", threads: function (c) { return Math.max(1, c - 1); }, duty: 1 }
  };

  function sha256hex(s) {
    return crypto.subtle.digest("SHA-256", new TextEncoder().encode(s)).then(function (b) {
      return Array.prototype.map.call(new Uint8Array(b), function (x) { return ("0" + x.toString(16)).slice(-2); }).join("");
    });
  }
  function fmt(n) { return Math.round(n).toLocaleString("en-US"); }

  function mount(el, fb, user) {
    var key = "qweb:" + user.uid;
    var st = { height: 0, prev: "0".repeat(64), blocks: 0 };
    try { st = Object.assign(st, JSON.parse(localStorage.getItem(key) || "{}")); } catch (e) {}
    var workers = [], running = false, rates = {}, addr = "…", mode = "light";

    el.innerHTML =
      '<h2>⛏️ Mine in your browser — 1 click</h2>' +
      '<p class="sub" style="margin-bottom:10px">No download, no upload. Press <b>START MINING</b> — everything runs in the background of this page. Keep this tab open while mining.</p>' +
      '<div class="stats">' +
      '<div class="stat"><div class="l">Status</div><div class="v" id="wmS">Stopped</div><div class="s" id="wmR">0 H/s</div></div>' +
      '<div class="stat"><div class="l">Web blocks found</div><div class="v" id="wmB">0</div><div class="s">this account</div></div>' +
      '<div class="stat"><div class="l">Web balance</div><div class="v" id="wmQ">0</div><div class="s">QSR (testnet)</div></div></div>' +
      '<p style="margin:12px 0 6px"><select id="wmM" style="padding:8px;border-radius:8px"></select></p>' +
      '<a class="btn" id="wmBtn" href="#" style="font-size:20px;padding:14px 44px;background:linear-gradient(180deg,#FFD54A,#F5A623);border:2px solid #B87700;color:#3A2500">⚡ START MINING</a>' +
      '<p id="wmMsg" style="font-size:12.5px;color:var(--mut);margin-top:10px">Testnet coins have no real money value. Web mining is lighter than the laptop miner, and its credits are tracked on your account (separate from the laptop P2P chain). Mining only runs while this page is open, and only after you press START.</p>';
    var $ = function (id) { return el.querySelector("#" + id); };
    Object.keys(MODES).forEach(function (k) {
      var o = document.createElement("option"); o.value = k; o.textContent = MODES[k].label; $("wmM").appendChild(o);
    });
    $("wmM").onchange = function () { mode = this.value; if (running) { halt(); begin(); } };
    sha256hex(user.uid).then(function (h) { addr = "QW" + h.slice(0, 38); });

    function paint() {
      var bal = QF.qsrAtHeight(st.blocks);
      $("wmB").textContent = fmt(st.blocks); $("wmQ").textContent = fmt(bal);
      var a = document.getElementById("wBal"), b = document.getElementById("wRew"), w = document.getElementById("wAddr");
      if (a) a.textContent = fmt(bal); if (b) b.textContent = fmt(st.blocks); if (w) w.textContent = addr;
    }
    function save() {
      try { localStorage.setItem(key, JSON.stringify(st)); } catch (e) {}
      try {
        fb.db.collection("users").doc(user.uid).set({
          webMined: { blocks: st.blocks, height: st.height, prev: st.prev, addr: addr, balance: QF.qsrAtHeight(st.blocks), ts: Math.floor(Date.now() / 1000) }
        }, { merge: true });
      } catch (e) {}
    }
    function halt() {
      workers.forEach(function (w) { try { w.postMessage({ type: "stop" }); w.terminate(); } catch (e) {} });
      workers = []; rates = {};
    }
    function begin() {
      var m = MODES[mode], n = m.threads(navigator.hardwareConcurrency || 2);
      var ch = [st.prev, st.height, P.bits, P.tag, Math.floor(Date.now() / 1000)].join("|");
      var url = URL.createObjectURL(new Blob([WORKER], { type: "application/javascript" }));
      for (var i = 0; i < n; i++) (function (id) {
        var w = new Worker(url); workers.push(w);
        w.onmessage = function (e) {
          var d = e.data;
          if (d.type === "rate") { rates[id] = d.n / (d.ms / 1000 * (m.duty < 1 ? 1 / m.duty : 1)); var t = 0; for (var k in rates) t += rates[k]; $("wmR").textContent = t.toFixed(1) + " H/s · " + n + " thread" + (n > 1 ? "s" : ""); }
          if (d.type === "found" && running) {
            halt(); st.prev = d.proof; st.height++; st.blocks++; paint(); save();
            $("wmMsg").textContent = "✅ Block #" + st.blocks + " found! +" + fmt(QF.qsrAtHeight(st.blocks) - QF.qsrAtHeight(st.blocks - 1)) + " QSR";
            begin();
          }
        };
        w.onerror = function () { stop("Could not load the mining engine — check your internet connection and try again."); };
        w.postMessage({ type: "go", challenge: ch, start: id, step: n, duty: m.duty, N: P.N, r: P.r, p: P.p, bits: P.bits });
      })(i);
    }
    function stop(msg) {
      running = false; halt(); $("wmS").textContent = "Stopped"; $("wmR").textContent = "0 H/s";
      $("wmBtn").textContent = "⚡ START MINING"; if (msg) $("wmMsg").textContent = msg; save();
    }
    $("wmBtn").onclick = function (e) {
      e.preventDefault();
      if (running) { stop("Stopped. Your coins are saved."); return; }
      if (!window.Worker) { $("wmMsg").textContent = "This browser can't run background mining."; return; }
      running = true; $("wmS").textContent = "Mining…"; this.textContent = "⏹ STOP MINING"; begin();
    };
    window.addEventListener("pagehide", function () { if (running) stop(); });
    paint(); save();
  }
  window.QWebMiner = { mount: mount };
})();
