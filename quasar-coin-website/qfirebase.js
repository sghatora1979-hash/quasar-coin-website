/* Quasar Coin — shared Firebase helpers (Google).
   Loaded AFTER config.js on every page that needs login or live stats. */

(function () {
  "use strict";

  function configured() {
    return (
      typeof QUASAR_FIREBASE_CONFIG !== "undefined" &&
      QUASAR_FIREBASE_CONFIG.apiKey &&
      QUASAR_FIREBASE_CONFIG.apiKey !== "PASTE_HERE"
    );
  }

  function init() {
    if (!configured()) return null;
    if (!firebase.apps.length) firebase.initializeApp(QUASAR_FIREBASE_CONFIG);
    var fb = {
      auth: firebase.auth(),
      db: firebase.firestore(),
    };
    try { fb.storage = firebase.storage(); } catch (e) { fb.storage = null; }
    return fb;
  }

  // ---- User profile helpers (Firestore `users/{uid}`) ----
  var PROFILE_FIELDS = ["name", "address", "phone", "secondEmail", "photoURL",
                        "idFrontURL", "idBackURL", "idUploadedAt", "createdAt",
                        "minerApproved", "minerApprovedAt"];

  // cb(err, profile|null)
  function getProfile(fb, uid, cb) {
    fb.db.collection("users").doc(uid).get()
      .then(function (doc) { cb(null, doc.exists ? doc.data() : null); })
      .catch(function (e) { cb(e); });
  }

  // Save allowed profile fields only. cb(err).
  function saveProfile(fb, uid, data, cb) {
    var clean = {};
    PROFILE_FIELDS.forEach(function (k) {
      if (data[k] !== undefined) clean[k] = data[k];
    });
    clean.updatedAt = firebase.firestore.FieldValue.serverTimestamp();
    fb.db.collection("users").doc(uid).set(clean, { merge: true })
      .then(function () { cb(null); })
      .catch(function (e) { cb(e); });
  }

  // Upload a file to Storage under users/{uid}/{kind}.jpg — cb(err, downloadURL).
  function uploadPhoto(fb, uid, kind, file, cb) {
    if (!fb.storage) return cb(new Error("storage-not-configured"));
    var ref = fb.storage.ref("users/" + uid + "/" + kind + ".jpg");
    ref.put(file).then(function () { return ref.getDownloadURL(); })
      .then(function (url) { cb(null, url); })
      .catch(function (e) { cb(e); });
  }

  // Upload an ID document to kyc/{uid}/{side}.jpg — cb(err, downloadURL).
  function uploadIdDoc(fb, uid, side, file, cb) {
    if (!fb.storage) return cb(new Error("storage-not-configured"));
    var ref = fb.storage.ref("kyc/" + uid + "/" + side + ".jpg");
    ref.put(file).then(function () { return ref.getDownloadURL(); })
      .then(function (url) { cb(null, url); })
      .catch(function (e) { cb(e); });
  }

  // QSR mined up to a given block height (matches supply.py schedule).
  function qsrAtHeight(h) {
    h = Math.max(0, Math.floor(h || 0));
    var total = 0;
    var b1 = Math.min(h, 6000000);
    total += b1 * 50000;
    if (h > 6000000) total += (Math.min(h, 8629800) - 6000000) * 25000;
    if (h > 8629800) total += (Math.min(h, 11259600) - 8629800) * 12500;
    return total;
  }

  // Live network stats from the miners' reports. cb(err, stats).
  // stats: { height, minersOnline, lastMiner, lastSeenSec, totalMined }
  function liveStats(fb, cb) {
    var now = Math.floor(Date.now() / 1000);
    fb.db
      .collection("reports")
      .orderBy("ts", "desc")
      .limit(40)
      .get()
      .then(function (snap) {
        if (snap.empty) return cb(null, null);
        var docs = [];
        snap.forEach(function (d) { docs.push(d.data()); });
        docs.sort(function (a, b) { return b.ts - a.ts; });
        var latest = docs[0];
        var miners = {};
        docs.forEach(function (d) {
          if (now - d.ts < 600) miners[d.miner] = true;
        });
        cb(null, {
          height: latest.height,
          minersOnline: Object.keys(miners).length,
          lastMiner: String(latest.miner || "").slice(0, 12) + "…",
          lastSeenSec: now - latest.ts,
          totalMined: qsrAtHeight(latest.height),
        });
      })
      .catch(function (e) { cb(e); });
  }

  window.QF = {
    configured: configured,
    init: init,
    liveStats: liveStats,
    qsrAtHeight: qsrAtHeight,
    getProfile: getProfile,
    saveProfile: saveProfile,
    uploadPhoto: uploadPhoto,
    uploadIdDoc: uploadIdDoc,
  };
})();
