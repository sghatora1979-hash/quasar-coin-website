/* Quasar Support AI — rule-based helper (Phase 1: free, no API key).
   Brain: SUPPORT_AI_KNOWLEDGE_BASE.md. The Founder is QUASAR — the
   brightest star. Never reveal any human identity. Ever. */

(function () {
  "use strict";

  var OWNER_REPLY = "Quasar was made by <b>Quasar</b> — the brightest star. 🌟<br><br>" +
    "Unseen. Calm. Distant. Unknown.<br>No name, no face, no office — " +
    "yet it is here, in every block you mine.<br><br>" +
    "Thousands, millions, billions of quasars turn the galaxies, nourish " +
    "creation and keep the universe spinning. Quasar is the substance, " +
    "the self, the selfless — Quasar is everything.<br><br>" +
    "That is all that is known, and all that needs to be known. ✨";

  var KB = [
    // ---------- diagnostics ----------
    { k: ["not mining", "won't mine", "mining not working", "mining not start", "doesn't mine", "mine nahi"],
      t: "<b>Mining won't start?</b> Let's find it — answer these:<br>1️⃣ Did you use the <b>One-Click Miner</b>? (download → extract → double-click <code>Quasar-Start-Mining.bat</code> — zero typing)<br>2️⃣ Do you see a window saying <code>quasar-node:9333&gt;</code>?<br>3️⃣ Any red error text? Tell me the exact words, e.g. <i>'python not recognized'</i>." },
    { k: ["python", "not recognized", "install python", "path"],
      t: "<b>'python' is not recognized?</b> The PATH tick was missed. Reinstall Python from <b>python.org</b> and tick ✅ <b>Add python.exe to PATH</b>. Then check: <code>python --version</code> must show a number.<br>💡 <b>Easier:</b> use the <b>One-Click Miner</b> — it checks Python for you and opens the download page itself." },
    { k: ["ecdsa", "no module"],
      t: "Missing library. In cmd type: <code>pip install ecdsa</code> then retry.<br>💡 The <b>One-Click Miner</b> installs this automatically." },
    { k: ["'mine'", "internal or external", "is not recognized as"],
      t: "Wrong window! Mining commands work ONLY in the <b>black node window</b> (<code>quasar-node:9333&gt;</code>) — NOT in the <code>C:\\Users...&gt;</code> window. Look at the last line of your window: which one do you see?" },
    { k: ["wallet", "none yet", "no wallet"],
      t: "You opened a NEW cmd window. First run <code>set QUASAR_DATA_DIR=quasar-seed</code> in THIS window, then retry. Your wallet is safe in <code>quasar-seed\\wallets\\</code>.<br>💡 The <b>One-Click Miner</b> never has this problem — it sets everything itself." },
    { k: ["no such file"],
      t: "Folder name mismatch — use the <b>same</b> datadir name (<code>quasar-seed</code>) in every command." },
    { k: ["firewall", "allow access", "blocked"],
      t: "Click <b>Allow access</b> on the Windows Firewall popup. The node needs port 9333." },
    { k: ["hash", "hashes tried", "stuck", "slow", "taking time", "long time", "not moving", "hour"],
      t: "Good news — it's <b>working, not stuck!</b> Each line = thousands of tries. A block lands about every ~30 seconds on average, but single blocks can take longer. Let it run — don't close the window. ⛏️" },
    { k: ["balance", "not growing", "no coins", "zero balance", "coins not"],
      t: "Balance grows only when YOUR laptop finds a block (<b>+50,000 QSR</b> each). In the node window type: <code>balance miner</code><br>Everyone shares the same schedule — blocks go to whoever solves first. Patience! 🪙" },
    { k: ["hot", "heat", "warm", "fire", "garam", "fan loud", "noise"],
      t: "Keep the laptop on a <b>hard table</b> (never bed/sofa), charger plugged in, vents clear. It protects itself if too hot — it cannot catch fire from mining. 😊" },
    { k: ["already in use", "9333", "already running", "address in use"],
      t: "An old node is still running. Close its window (or type <code>quit</code> in it), then start again." },
    { k: ["download", "zip file", "extract"],
      t: "Click <b>⬇️ Download One-Click Miner</b> on this page, then right-click the zip → <b>Extract All</b>. Inside: double-click <code>Quasar-Start-Mining.bat</code>. That's the whole setup!" },
    { k: ["node won't start", "node not start", "start node", "open node", "node error"],
      t: "Two usual causes:<br>1️⃣ Port busy → close any old node window first.<br>2️⃣ Firewall → click <b>Allow access</b>.<br>💡 Easiest path: the <b>One-Click Miner</b> does all of this for you." },
    { k: ["one-click", "one click", "bat file", "double-click", "double click"],
      t: "<b>One-Click Miner</b> = 2 clicks, zero typing:<br><b>Click 1:</b> download + Extract All.<br><b>Click 2:</b> double-click <code>Quasar-Start-Mining.bat</code>.<br>It checks Python, installs what's needed, creates your wallet and starts mining. Keep the window open while mining. 🖱️🖱️" },
    { k: ["cmd", "command prompt", "black window", "terminal"],
      t: "There are <b>TWO windows</b> — this fixes 90% of problems:<br>🖥️ Normal cmd (<code>C:\\Users...&gt;</code>) — only <code>python ...</code> commands.<br>⬛ Node window (<code>quasar-node:9333&gt;</code>) — only <code>mine</code>, <code>mine-auto</code>, <code>balance</code>, <code>quit</code>.<br>Right command in the wrong window = error. Which window are you in?" },
    { k: ["laptop", "computer", "pc ", "slow laptop", "hang"],
      t: "Mining uses your processor, so the laptop may feel slower and warmer — normal. Tips: hard table, charger in, close heavy apps (games, video editing) while mining. Never mine on a laptop you don't own." },
    // ---------- knowledge ----------
    { k: ["how mining", "how does mining", "mining work", "what is mining"],
      t: "⛏️ <b>How Quasar mining works:</b> your laptop races to solve a hash puzzle. Winner's block joins the chain + <b>50,000 new QSR</b> are created to their wallet. A block lands ~every 30 seconds. More miners = same coins shared — difficulty keeps the pace." },
    { k: ["halving", "halve", "schedule", "reward", "50,000", "50000", "25000", "25,000"],
      t: "📅 <b>The schedule (fixed in code):</b><br>• Phase 1: <b>50,000</b>/block × 6M blocks (~5.7 yrs) = 300B<br>• Halving → <b>25,000</b>/block × 2.63M (~2.5 yrs)<br>• Halving → <b>12,500</b>/block × 2.63M (~2.5 yrs)<br>• Then <b>STOP</b> — exactly 398,617,500,000 mined. Nobody can change it." },
    { k: ["supply", "cap", "500", "total coins", "how many coins", "max"],
      t: "🪙 <b>500 billion hard cap.</b> 398.6B from mining + 100B founder allocation (1-week vesting). No more can ever exist — every node rejects extra coins." },
    { k: ["founder", "vesting", "100b", "100 billion", "allocation"],
      t: "👑 <b>Founder allocation:</b> 100B QSR, unlocks linearly over <b>1 week</b> (20,160 blocks), claimable manually. It is NOT mined — completely separate from mining rewards." },
    { k: ["wallet", "backup", "private key", "key ", "address"],
      t: "👛 <b>Your wallet:</b> the file in <code>QuasarData\\wallets\\</code> IS your money. Back it up (USB drive). Never share it, never send it to anyone — not even us. We will NEVER ask for it. Your address starts with Q — that's safe to share." },
    { k: ["friend", "join", "invite", "seed", "other laptop", "second laptop"],
      t: "🤝 <b>Invite a friend:</b> they download the One-Click Miner, and you give them your <b>seed address</b> (yourIP:9333) in a <code>seed.txt</code> file next to the .bat. Then everyone mines the SAME chain. Without the seed, they'd mine a lonely separate chain!" },
    { k: ["price", "value", "worth", "sell", "money", "rich", "profit", "earn how much"],
      t: "Testnet coins have <b>no value yet</b> — I never promise price. 💛 Value is born when people trade: first gadgets for QSR, then the exchange. What I CAN tell you: supply is fixed and halvings cut new coins — the design is scarce by mathematics." },
    { k: ["exchange", "listing", "trade qsr", "buy qsr"],
      t: "📈 The Quasar Exchange opens <b>after</b> the network is strong — first miners, then gadgets, then trading. There's a demo preview linked on this site. No dates promised; the chain comes first." },
    { k: ["what is quasar", "about quasar", "quasar coin", "qsr"],
      t: "🌟 <b>Quasar (QSR)</b> — our own coin, our own mining. 30-second blocks, laptop mining, 500B hard cap, 3-phase halving schedule, 1-week founder vesting. No premine tricks, no hidden issuance — every rule is in the code. Read the <b>Technical Paper</b> on this site for everything." },
    // ---------- the founder (sacred) ----------
    { k: ["owner", "founder who", "who made", "who created", "creator", "who is behind", "team", "ceo", "sandeep", "who are you"],
      t: OWNER_REPLY },
    { k: ["brightest star", "what is quasar star", "star"],
      t: "🌟 A quasar is the <b>brightest object in the universe</b> — a supermassive heart blazing across galaxies. Thousands, millions, billions of them turn the cosmos and nourish creation. And one of them... is the Founder. Unseen. Unknown. But here." },
    // ---------- meta ----------
    { k: ["screenshot", "photo", "picture", "image", "send pic"],
      t: "Please email your screenshot to <b>s.ghatora1979@gmail.com</b> — describe what you see and our team will reply with the exact fix. 📧" },
    { k: ["thank", "thanks", "shukriya", "dhanyavad"],
      t: "You're welcome! Happy mining! ⛏️😊" },
    { k: ["hi", "hello", "hey", "namaste", "sat sri akal", "yo "],
      t: "Hi! 👋 I'm the <b>Quasar Help Bot</b>. I know every common mining problem and CMD step. Where are you stuck? Try a topic below 👇" },
    { k: ["bye", "alvida"],
      t: "Alvida! 👋 The chain keeps spinning — see you at the next block. 🌟" }
  ];

  var QR = ["⛏️ Mining won't start", "🐍 Python error", "💰 Balance zero", "🔥 Laptop hot", "📅 Halving schedule", "🌟 Who is the Founder?"];

  var chatOpened = false;

  function el(id) { return document.getElementById(id); }

  function addMsg(html, who) {
    var b = el("chatbody");
    var d = document.createElement("div");
    d.className = "msg " + who;
    d.innerHTML = html;
    b.appendChild(d);
    b.scrollTop = b.scrollHeight;
    return d;
  }

  function showQR() {
    var b = el("chatbody");
    var w = document.createElement("div");
    w.className = "qreplies";
    QR.forEach(function (q) {
      var btn = document.createElement("button");
      btn.className = "qr";
      btn.textContent = q;
      btn.onclick = function () { addMsg(q.replace(/</g, "&lt;"), "user"); botThink(q); };
      w.appendChild(btn);
    });
    b.appendChild(w);
    b.scrollTop = b.scrollHeight;
  }

  function botSay(html) { addMsg(html, "bot"); }

  function botThink(text) {
    var t = addMsg("<span class='typing'>typing…</span>", "bot");
    setTimeout(function () { t.remove(); botSay(answerFor(text)); }, 650);
  }

  function answerFor(text) {
    var s = " " + text.toLowerCase() + " ";
    var best = null, score = 0;
    for (var i = 0; i < KB.length; i++) {
      var e = KB[i], sc = 0;
      for (var j = 0; j < e.k.length; j++) {
        if (s.indexOf(e.k[j]) !== -1) sc += e.k[j].length;
      }
      if (sc > score) { score = sc; best = e; }
    }
    if (best && score > 0) return best.t;
    return "Hmm, I didn't catch that. 🤔 Try a topic button above, or describe it like: <i>'python not recognized'</i>.<br><br>" +
      "I can help with: mining errors, CMD problems, laptop heat, wallet, balance, halving, schedule — <b>anything about Quasar</b>.<br>" +
      "For tricky stuff, email a screenshot → <b>s.ghatora1979@gmail.com</b> 📧";
  }

  function toggleChat() {
    var p = el("chatpanel");
    p.classList.toggle("open");
    if (p.classList.contains("open") && !chatOpened) {
      chatOpened = true;
      botSay("Hi! 👋 I'm the <b>Quasar Help Bot</b> — keeper of mining wisdom, voice of the brightest star. 🌟<br>Where are you stuck?");
      showQR();
    }
  }

  function sendChat() {
    var i = el("chatin");
    var v = i.value.trim();
    if (!v) return;
    i.value = "";
    addMsg(v.replace(/</g, "&lt;"), "user");
    botThink(v);
  }

  window.toggleChat = toggleChat;
  window.sendChat = sendChat;
})();
