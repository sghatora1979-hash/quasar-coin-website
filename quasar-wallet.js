/* ============================================================================
 * QUASAR WALLET LIBRARY (browser, zero dependencies)
 * ----------------------------------------------------------------------------
 * - BIP39 24-word phrases (256-bit entropy used DIRECTLY as the secp256k1
 *   private key, so web wallets and the Python miner derive IDENTICAL keys)
 * - secp256k1 public-key derivation (BigInt, pure JS)
 * - Quasar addresses: Base58Check(0x3A + ripemd160(sha256(compr_pubkey)))
 *   (byte-identical to Python wallet.py -> every address starts with 'Q')
 *
 * SECURITY: phrases and private keys NEVER leave this browser tab.
 * Only the public address is ever sent anywhere (e.g. saved to Firestore).
 * ========================================================================== */
(function (global) {
  "use strict";

  var WORDLIST = [
"abandon","ability","able","about","above","absent","absorb","abstract",
"absurd","abuse","access","accident","account","accuse","achieve","acid",
"acoustic","acquire","across","act","action","actor","actress","actual",
"adapt","add","addict","address","adjust","admit","adult","advance",
"advice","aerobic","affair","afford","afraid","again","age","agent",
"agree","ahead","aim","air","airport","aisle","alarm","album",
"alcohol","alert","alien","all","alley","allow","almost","alone",
"alpha","already","also","alter","always","amateur","amazing","among",
"amount","amused","analyst","anchor","ancient","anger","angle","angry",
"animal","ankle","announce","annual","another","answer","antenna","antique",
"anxiety","any","apart","apology","appear","apple","approve","april",
"arch","arctic","area","arena","argue","arm","armed","armor",
"army","around","arrange","arrest","arrive","arrow","art","artefact",
"artist","artwork","ask","aspect","assault","asset","assist","assume",
"asthma","athlete","atom","attack","attend","attitude","attract","auction",
"audit","august","aunt","author","auto","autumn","average","avocado",
"avoid","awake","aware","away","awesome","awful","awkward","axis",
"baby","bachelor","bacon","badge","bag","balance","balcony","ball",
"bamboo","banana","banner","bar","barely","bargain","barrel","base",
"basic","basket","battle","beach","bean","beauty","because","become",
"beef","before","begin","behave","behind","believe","below","belt",
"bench","benefit","best","betray","better","between","beyond","bicycle",
"bid","bike","bind","biology","bird","birth","bitter","black",
"blade","blame","blanket","blast","bleak","bless","blind","blood",
"blossom","blouse","blue","blur","blush","board","boat","body",
"boil","bomb","bone","bonus","book","boost","border","boring",
"borrow","boss","bottom","bounce","box","boy","bracket","brain",
"brand","brass","brave","bread","breeze","brick","bridge","brief",
"bright","bring","brisk","broccoli","broken","bronze","broom","brother",
"brown","brush","bubble","buddy","budget","buffalo","build","bulb",
"bulk","bullet","bundle","bunker","burden","burger","burst","bus",
"business","busy","butter","buyer","buzz","cabbage","cabin","cable",
"cactus","cage","cake","call","calm","camera","camp","can",
"canal","cancel","candy","cannon","canoe","canvas","canyon","capable",
"capital","captain","car","carbon","card","cargo","carpet","carry",
"cart","case","cash","casino","castle","casual","cat","catalog",
"catch","category","cattle","caught","cause","caution","cave","ceiling",
"celery","cement","census","century","cereal","certain","chair","chalk",
"champion","change","chaos","chapter","charge","chase","chat","cheap",
"check","cheese","chef","cherry","chest","chicken","chief","child",
"chimney","choice","choose","chronic","chuckle","chunk","churn","cigar",
"cinnamon","circle","citizen","city","civil","claim","clap","clarify",
"claw","clay","clean","clerk","clever","click","client","cliff",
"climb","clinic","clip","clock","clog","close","cloth","cloud",
"clown","club","clump","cluster","clutch","coach","coast","coconut",
"code","coffee","coil","coin","collect","color","column","combine",
"come","comfort","comic","common","company","concert","conduct","confirm",
"congress","connect","consider","control","convince","cook","cool","copper",
"copy","coral","core","corn","correct","cost","cotton","couch",
"country","couple","course","cousin","cover","coyote","crack","cradle",
"craft","cram","crane","crash","crater","crawl","crazy","cream",
"credit","creek","crew","cricket","crime","crisp","critic","crop",
"cross","crouch","crowd","crucial","cruel","cruise","crumble","crunch",
"crush","cry","crystal","cube","culture","cup","cupboard","curious",
"current","curtain","curve","cushion","custom","cute","cycle","dad",
"damage","damp","dance","danger","daring","dash","daughter","dawn",
"day","deal","debate","debris","decade","december","decide","decline",
"decorate","decrease","deer","defense","define","defy","degree","delay",
"deliver","demand","demise","denial","dentist","deny","depart","depend",
"deposit","depth","deputy","derive","describe","desert","design","desk",
"despair","destroy","detail","detect","develop","device","devote","diagram",
"dial","diamond","diary","dice","diesel","diet","differ","digital",
"dignity","dilemma","dinner","dinosaur","direct","dirt","disagree","discover",
"disease","dish","dismiss","disorder","display","distance","divert","divide",
"divorce","dizzy","doctor","document","dog","doll","dolphin","domain",
"donate","donkey","donor","door","dose","double","dove","draft",
"dragon","drama","drastic","draw","dream","dress","drift","drill",
"drink","drip","drive","drop","drum","dry","duck","dumb",
"dune","during","dust","dutch","duty","dwarf","dynamic","eager",
"eagle","early","earn","earth","easily","east","easy","echo",
"ecology","economy","edge","edit","educate","effort","egg","eight",
"either","elbow","elder","electric","elegant","element","elephant","elevator",
"elite","else","embark","embody","embrace","emerge","emotion","employ",
"empower","empty","enable","enact","end","endless","endorse","enemy",
"energy","enforce","engage","engine","enhance","enjoy","enlist","enough",
"enrich","enroll","ensure","enter","entire","entry","envelope","episode",
"equal","equip","era","erase","erode","erosion","error","erupt",
"escape","essay","essence","estate","eternal","ethics","evidence","evil",
"evoke","evolve","exact","example","excess","exchange","excite","exclude",
"excuse","execute","exercise","exhaust","exhibit","exile","exist","exit",
"exotic","expand","expect","expire","explain","expose","express","extend",
"extra","eye","eyebrow","fabric","face","faculty","fade","faint",
"faith","fall","false","fame","family","famous","fan","fancy",
"fantasy","farm","fashion","fat","fatal","father","fatigue","fault",
"favorite","feature","february","federal","fee","feed","feel","female",
"fence","festival","fetch","fever","few","fiber","fiction","field",
"figure","file","film","filter","final","find","fine","finger",
"finish","fire","firm","first","fiscal","fish","fit","fitness",
"fix","flag","flame","flash","flat","flavor","flee","flight",
"flip","float","flock","floor","flower","fluid","flush","fly",
"foam","focus","fog","foil","fold","follow","food","foot",
"force","forest","forget","fork","fortune","forum","forward","fossil",
"foster","found","fox","fragile","frame","frequent","fresh","friend",
"fringe","frog","front","frost","frown","frozen","fruit","fuel",
"fun","funny","furnace","fury","future","gadget","gain","galaxy",
"gallery","game","gap","garage","garbage","garden","garlic","garment",
"gas","gasp","gate","gather","gauge","gaze","general","genius",
"genre","gentle","genuine","gesture","ghost","giant","gift","giggle",
"ginger","giraffe","girl","give","glad","glance","glare","glass",
"glide","glimpse","globe","gloom","glory","glove","glow","glue",
"goat","goddess","gold","good","goose","gorilla","gospel","gossip",
"govern","gown","grab","grace","grain","grant","grape","grass",
"gravity","great","green","grid","grief","grit","grocery","group",
"grow","grunt","guard","guess","guide","guilt","guitar","gun",
"gym","habit","hair","half","hammer","hamster","hand","happy",
"harbor","hard","harsh","harvest","hat","have","hawk","hazard",
"head","health","heart","heavy","hedgehog","height","hello","helmet",
"help","hen","hero","hidden","high","hill","hint","hip",
"hire","history","hobby","hockey","hold","hole","holiday","hollow",
"home","honey","hood","hope","horn","horror","horse","hospital",
"host","hotel","hour","hover","hub","huge","human","humble",
"humor","hundred","hungry","hunt","hurdle","hurry","hurt","husband",
"hybrid","ice","icon","idea","identify","idle","ignore","ill",
"illegal","illness","image","imitate","immense","immune","impact","impose",
"improve","impulse","inch","include","income","increase","index","indicate",
"indoor","industry","infant","inflict","inform","inhale","inherit","initial",
"inject","injury","inmate","inner","innocent","input","inquiry","insane",
"insect","inside","inspire","install","intact","interest","into","invest",
"invite","involve","iron","island","isolate","issue","item","ivory",
"jacket","jaguar","jar","jazz","jealous","jeans","jelly","jewel",
"job","join","joke","journey","joy","judge","juice","jump",
"jungle","junior","junk","just","kangaroo","keen","keep","ketchup",
"key","kick","kid","kidney","kind","kingdom","kiss","kit",
"kitchen","kite","kitten","kiwi","knee","knife","knock","know",
"lab","label","labor","ladder","lady","lake","lamp","language",
"laptop","large","later","latin","laugh","laundry","lava","law",
"lawn","lawsuit","layer","lazy","leader","leaf","learn","leave",
"lecture","left","leg","legal","legend","leisure","lemon","lend",
"length","lens","leopard","lesson","letter","level","liar","liberty",
"library","license","life","lift","light","like","limb","limit",
"link","lion","liquid","list","little","live","lizard","load",
"loan","lobster","local","lock","logic","lonely","long","loop",
"lottery","loud","lounge","love","loyal","lucky","luggage","lumber",
"lunar","lunch","luxury","lyrics","machine","mad","magic","magnet",
"maid","mail","main","major","make","mammal","man","manage",
"mandate","mango","mansion","manual","maple","marble","march","margin",
"marine","market","marriage","mask","mass","master","match","material",
"math","matrix","matter","maximum","maze","meadow","mean","measure",
"meat","mechanic","medal","media","melody","melt","member","memory",
"mention","menu","mercy","merge","merit","merry","mesh","message",
"metal","method","middle","midnight","milk","million","mimic","mind",
"minimum","minor","minute","miracle","mirror","misery","miss","mistake",
"mix","mixed","mixture","mobile","model","modify","mom","moment",
"monitor","monkey","monster","month","moon","moral","more","morning",
"mosquito","mother","motion","motor","mountain","mouse","move","movie",
"much","muffin","mule","multiply","muscle","museum","mushroom","music",
"must","mutual","myself","mystery","myth","naive","name","napkin",
"narrow","nasty","nation","nature","near","neck","need","negative",
"neglect","neither","nephew","nerve","nest","net","network","neutral",
"never","news","next","nice","night","noble","noise","nominee",
"noodle","normal","north","nose","notable","note","nothing","notice",
"novel","now","nuclear","number","nurse","nut","oak","obey",
"object","oblige","obscure","observe","obtain","obvious","occur","ocean",
"october","odor","off","offer","office","often","oil","okay",
"old","olive","olympic","omit","once","one","onion","online",
"only","open","opera","opinion","oppose","option","orange","orbit",
"orchard","order","ordinary","organ","orient","original","orphan","ostrich",
"other","outdoor","outer","output","outside","oval","oven","over",
"own","owner","oxygen","oyster","ozone","pact","paddle","page",
"pair","palace","palm","panda","panel","panic","panther","paper",
"parade","parent","park","parrot","party","pass","patch","path",
"patient","patrol","pattern","pause","pave","payment","peace","peanut",
"pear","peasant","pelican","pen","penalty","pencil","people","pepper",
"perfect","permit","person","pet","phone","photo","phrase","physical",
"piano","picnic","picture","piece","pig","pigeon","pill","pilot",
"pink","pioneer","pipe","pistol","pitch","pizza","place","planet",
"plastic","plate","play","please","pledge","pluck","plug","plunge",
"poem","poet","point","polar","pole","police","pond","pony",
"pool","popular","portion","position","possible","post","potato","pottery",
"poverty","powder","power","practice","praise","predict","prefer","prepare",
"present","pretty","prevent","price","pride","primary","print","priority",
"prison","private","prize","problem","process","produce","profit","program",
"project","promote","proof","property","prosper","protect","proud","provide",
"public","pudding","pull","pulp","pulse","pumpkin","punch","pupil",
"puppy","purchase","purity","purpose","purse","push","put","puzzle",
"pyramid","quality","quantum","quarter","question","quick","quit","quiz",
"quote","rabbit","raccoon","race","rack","radar","radio","rail",
"rain","raise","rally","ramp","ranch","random","range","rapid",
"rare","rate","rather","raven","raw","razor","ready","real",
"reason","rebel","rebuild","recall","receive","recipe","record","recycle",
"reduce","reflect","reform","refuse","region","regret","regular","reject",
"relax","release","relief","rely","remain","remember","remind","remove",
"render","renew","rent","reopen","repair","repeat","replace","report",
"require","rescue","resemble","resist","resource","response","result","retire",
"retreat","return","reunion","reveal","review","reward","rhythm","rib",
"ribbon","rice","rich","ride","ridge","rifle","right","rigid",
"ring","riot","ripple","risk","ritual","rival","river","road",
"roast","robot","robust","rocket","romance","roof","rookie","room",
"rose","rotate","rough","round","route","royal","rubber","rude",
"rug","rule","run","runway","rural","sad","saddle","sadness",
"safe","sail","salad","salmon","salon","salt","salute","same",
"sample","sand","satisfy","satoshi","sauce","sausage","save","say",
"scale","scan","scare","scatter","scene","scheme","school","science",
"scissors","scorpion","scout","scrap","screen","script","scrub","sea",
"search","season","seat","second","secret","section","security","seed",
"seek","segment","select","sell","seminar","senior","sense","sentence",
"series","service","session","settle","setup","seven","shadow","shaft",
"shallow","share","shed","shell","sheriff","shield","shift","shine",
"ship","shiver","shock","shoe","shoot","shop","short","shoulder",
"shove","shrimp","shrug","shuffle","shy","sibling","sick","side",
"siege","sight","sign","silent","silk","silly","silver","similar",
"simple","since","sing","siren","sister","situate","six","size",
"skate","sketch","ski","skill","skin","skirt","skull","slab",
"slam","sleep","slender","slice","slide","slight","slim","slogan",
"slot","slow","slush","small","smart","smile","smoke","smooth",
"snack","snake","snap","sniff","snow","soap","soccer","social",
"sock","soda","soft","solar","soldier","solid","solution","solve",
"someone","song","soon","sorry","sort","soul","sound","soup",
"source","south","space","spare","spatial","spawn","speak","special",
"speed","spell","spend","sphere","spice","spider","spike","spin",
"spirit","split","spoil","sponsor","spoon","sport","spot","spray",
"spread","spring","spy","square","squeeze","squirrel","stable","stadium",
"staff","stage","stairs","stamp","stand","start","state","stay",
"steak","steel","stem","step","stereo","stick","still","sting",
"stock","stomach","stone","stool","story","stove","strategy","street",
"strike","strong","struggle","student","stuff","stumble","style","subject",
"submit","subway","success","such","sudden","suffer","sugar","suggest",
"suit","summer","sun","sunny","sunset","super","supply","supreme",
"sure","surface","surge","surprise","surround","survey","suspect","sustain",
"swallow","swamp","swap","swarm","swear","sweet","swift","swim",
"swing","switch","sword","symbol","symptom","syrup","system","table",
"tackle","tag","tail","talent","talk","tank","tape","target",
"task","taste","tattoo","taxi","teach","team","tell","ten",
"tenant","tennis","tent","term","test","text","thank","that",
"theme","then","theory","there","they","thing","this","thought",
"three","thrive","throw","thumb","thunder","ticket","tide","tiger",
"tilt","timber","time","tiny","tip","tired","tissue","title",
"toast","tobacco","today","toddler","toe","together","toilet","token",
"tomato","tomorrow","tone","tongue","tonight","tool","tooth","top",
"topic","topple","torch","tornado","tortoise","toss","total","tourist",
"toward","tower","town","toy","track","trade","traffic","tragic",
"train","transfer","trap","trash","travel","tray","treat","tree",
"trend","trial","tribe","trick","trigger","trim","trip","trophy",
"trouble","truck","true","truly","trumpet","trust","truth","try",
"tube","tuition","tumble","tuna","tunnel","turkey","turn","turtle",
"twelve","twenty","twice","twin","twist","two","type","typical",
"ugly","umbrella","unable","unaware","uncle","uncover","under","undo",
"unfair","unfold","unhappy","uniform","unique","unit","universe","unknown",
"unlock","until","unusual","unveil","update","upgrade","uphold","upon",
"upper","upset","urban","urge","usage","use","used","useful",
"useless","usual","utility","vacant","vacuum","vague","valid","valley",
"valve","van","vanish","vapor","various","vast","vault","vehicle",
"velvet","vendor","venture","venue","verb","verify","version","very",
"vessel","veteran","viable","vibrant","vicious","victory","video","view",
"village","vintage","violin","virtual","virus","visa","visit","visual",
"vital","vivid","vocal","voice","void","volcano","volume","vote",
"voyage","wage","wagon","wait","walk","wall","walnut","want",
"warfare","warm","warrior","wash","wasp","waste","water","wave",
"way","wealth","weapon","wear","weasel","weather","web","wedding",
"weekend","weird","welcome","west","wet","whale","what","wheat",
"wheel","when","where","whip","whisper","wide","width","wife",
"wild","will","win","window","wine","wing","wink","winner",
"winter","wire","wisdom","wise","wish","witness","wolf","woman",
"wonder","wood","wool","word","work","world","worry","worth",
"wrap","wreck","wrestle","wrist","write","wrong","yard","year",
"yellow","you","young","youth","zebra","zero","zone","zoo"
]; // replaced at build time with the 2048-word array

  // ------------------------------------------------------------------ utils
  function bytesToHex(b) {
    return Array.from(b).map(function (x) { return x.toString(16).padStart(2, "0"); }).join("");
  }
  function hexToBytes(h) {
    var b = new Uint8Array(h.length / 2);
    for (var i = 0; i < b.length; i++) b[i] = parseInt(h.substr(i * 2, 2), 16);
    return b;
  }
  function concat() {
    var total = 0, i;
    for (i = 0; i < arguments.length; i++) total += arguments[i].length;
    var out = new Uint8Array(total), off = 0;
    for (i = 0; i < arguments.length; i++) { out.set(arguments[i], off); off += arguments[i].length; }
    return out;
  }
  function rotr(x, n) { return ((x >>> n) | (x << (32 - n))) >>> 0; }

  // ------------------------------------------------------------------ SHA256
  var SHA256_K = [
    0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
    0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
    0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
    0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
    0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
    0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
    0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
    0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
  ];
  function sha256(data) {
    var h0=0x6a09e667,h1=0xbb67ae85,h2=0x3c6ef372,h3=0xa54ff53a,
        h4=0x510e527f,h5=0x9b05688c,h6=0x1f83d9ab,h7=0x5be0cd19;
    var ml = data.length, bitLenHi = Math.floor((ml / 0x20000000) >>> 0), bitLenLo = (ml << 3) >>> 0;
    var padded = Math.ceil((ml + 9) / 64) * 64, msg = new Uint8Array(padded);
    msg.set(data);
    msg[ml] = 0x80;
    msg[padded-8]=(bitLenHi>>>24)&255; msg[padded-7]=(bitLenHi>>>16)&255;
    msg[padded-6]=(bitLenHi>>>8)&255;  msg[padded-5]=bitLenHi&255;
    msg[padded-4]=(bitLenLo>>>24)&255; msg[padded-3]=(bitLenLo>>>16)&255;
    msg[padded-2]=(bitLenLo>>>8)&255;  msg[padded-1]=bitLenLo&255;
    var w = new Uint32Array(64), i, j;
    for (i = 0; i < padded; i += 64) {
      for (j = 0; j < 16; j++) w[j] = (msg[i+j*4]<<24)|(msg[i+j*4+1]<<16)|(msg[i+j*4+2]<<8)|msg[i+j*4+3];
      for (j = 16; j < 64; j++) {
        var s0 = rotr(w[j-15],7)^rotr(w[j-15],18)^(w[j-15]>>>3);
        var s1 = rotr(w[j-2],17)^rotr(w[j-2],19)^(w[j-2]>>>10);
        w[j] = (w[j-16]+s0+w[j-7]+s1)>>>0;
      }
      var a=h0,b=h1,c=h2,d=h3,e=h4,f=h5,g=h6,h=h7;
      for (j = 0; j < 64; j++) {
        var S1=rotr(e,6)^rotr(e,11)^rotr(e,25), ch=(e&f)^(~e&g);
        var t1=(h+S1+ch+SHA256_K[j]+w[j])>>>0;
        var S0=rotr(a,2)^rotr(a,13)^rotr(a,22), mj=(a&b)^(a&c)^(b&c);
        var t2=(S0+mj)>>>0;
        h=g; g=f; f=e; e=(d+t1)>>>0; d=c; c=b; b=a; a=(t1+t2)>>>0;
      }
      h0=(h0+a)>>>0; h1=(h1+b)>>>0; h2=(h2+c)>>>0; h3=(h3+d)>>>0;
      h4=(h4+e)>>>0; h5=(h5+f)>>>0; h6=(h6+g)>>>0; h7=(h7+h)>>>0;
    }
    var out = new Uint8Array(32), hh=[h0,h1,h2,h3,h4,h5,h6,h7];
    for (i = 0; i < 8; i++) { out[i*4]=hh[i]>>>24; out[i*4+1]=(hh[i]>>>16)&255; out[i*4+2]=(hh[i]>>>8)&255; out[i*4+3]=hh[i]&255; }
    return out;
  }

  // --------------------------------------------------------------- RIPEMD160
  var RMD_KL = [0x00000000,0x5a827999,0x6ed9eba1,0x8f1bbcdc,0xa953fd4e];
  var RMD_KR = [0x50a28be6,0x5c4dd124,0x6d703ef3,0x7a6d76e9,0x00000000];
  var RMD_RL = [
    0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,
    7,4,13,1,10,6,15,3,12,0,9,5,2,14,11,8,
    3,10,14,4,9,15,8,1,2,7,0,6,13,11,5,12,
    1,9,11,10,0,8,12,4,13,3,7,15,14,5,6,2,
    4,0,5,9,7,12,2,10,14,1,3,8,11,6,15,13];
  var RMD_RR = [
    5,14,7,0,9,2,11,4,13,6,15,8,1,10,3,12,
    6,11,3,7,0,13,5,10,14,15,8,12,4,9,1,2,
    15,5,1,3,7,14,6,9,11,8,12,2,10,0,4,13,
    8,6,4,1,3,11,15,0,5,12,2,13,9,7,10,14,
    12,15,10,4,1,5,8,7,6,2,13,14,0,3,9,11];
  var RMD_SL = [
    11,14,15,12,5,8,7,9,11,13,14,15,6,7,9,8,
    7,6,8,13,11,9,7,15,7,12,15,9,11,7,13,12,
    11,13,6,7,14,9,13,15,14,8,13,6,5,12,7,5,
    11,12,14,15,14,15,9,8,9,14,5,6,8,6,5,12,
    9,15,5,11,6,8,13,12,5,12,13,14,11,8,5,6];
  var RMD_SR = [
    8,9,9,11,13,15,15,5,7,7,8,11,14,14,12,6,
    9,13,15,7,12,8,9,11,7,7,12,7,6,15,13,11,
    9,7,15,11,8,6,6,14,12,13,5,14,13,13,7,5,
    15,5,8,11,14,14,6,14,6,9,12,9,12,5,15,8,
    8,5,12,9,12,5,14,6,8,13,6,5,15,13,11,11];
  function rmdF(j, x, y, z) {
    if (j < 16) return (x ^ y ^ z) >>> 0;
    if (j < 32) return ((x & y) | (~x & z)) >>> 0;
    if (j < 48) return ((x | ~y) ^ z) >>> 0;
    if (j < 64) return ((x & z) | (y & ~z)) >>> 0;
    return (x ^ (y | ~z)) >>> 0;
  }
  function rol(x, n) { return ((x << n) | (x >>> (32 - n))) >>> 0; }
  function ripemd160(data) {
    var h0=0x67452301,h1=0xefcdab89,h2=0x98badcfe,h3=0x10325476,h4=0xc3d2e1f0;
    var ml=data.length, bitLenLo=(ml<<3)>>>0, bitLenHi=(ml/0x20000000)>>>0;
    var padded=Math.ceil((ml+9)/64)*64, msg=new Uint8Array(padded);
    msg.set(data); msg[ml]=0x80;
    msg[padded-8]=bitLenLo&255; msg[padded-7]=(bitLenLo>>>8)&255;
    msg[padded-6]=(bitLenLo>>>16)&255; msg[padded-5]=(bitLenLo>>>24)&255;
    msg[padded-4]=bitLenHi&255; msg[padded-3]=(bitLenHi>>>8)&255;
    msg[padded-2]=(bitLenHi>>>16)&255; msg[padded-1]=(bitLenHi>>>24)&255;
    var X=new Uint32Array(16), i, j;
    for (i=0;i<padded;i+=64) {
      for (j=0;j<16;j++) X[j]=msg[i+j*4]|(msg[i+j*4+1]<<8)|(msg[i+j*4+2]<<16)|(msg[i+j*4+3]<<24);
      var a1=h0,b1=h1,c1=h2,d1=h3,e1=h4, a2=h0,b2=h1,c2=h2,d2=h3,e2=h4, t;
      for (j=0;j<80;j++) {
        t=(a1+rmdF(j,b1,c1,d1)+X[RMD_RL[j]]+RMD_KL[j>>4])>>>0;
        t=(rol(t,RMD_SL[j])+e1)>>>0; a1=e1; e1=d1; d1=rol(c1,10); c1=b1; b1=t;
        t=(a2+rmdF(79-j,b2,c2,d2)+X[RMD_RR[j]]+RMD_KR[j>>4])>>>0;
        t=(rol(t,RMD_SR[j])+e2)>>>0; a2=e2; e2=d2; d2=rol(c2,10); c2=b2; b2=t;
      }
      t=(h1+c1+d2)>>>0; h1=(h2+d1+e2)>>>0; h2=(h3+e1+a2)>>>0;
      h3=(h4+a1+b2)>>>0; h4=(h0+b1+c2)>>>0; h0=t;
    }
    var out=new Uint8Array(20), hh=[h0,h1,h2,h3,h4];
    for (i=0;i<5;i++){ out[i*4]=hh[i]&255; out[i*4+1]=(hh[i]>>>8)&255; out[i*4+2]=(hh[i]>>>16)&255; out[i*4+3]=(hh[i]>>>24)&255; }
    return out;
  }

  // --------------------------------------------------------------- secp256k1
  var P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2Fn;
  var GX = 0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798n;
  var GY = 0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8n;
  function modInv(a, m) {
    var lm=1n, hm=0n, low=((a%m)+m)%m, high=m;
    while (low > 1n) {
      var r = high/low, nm = hm - lm*r, nw = high - low*r;
      hm=lm; lm=nm; high=low; low=nw;
    }
    return ((lm % m) + m) % m;
  }
  // scalar mult: k * G, returns {x, y}
  function secp256k1Mul(k) {
    var rx=null, ry=null, qx=GX, qy=GY, kk=k;
    while (kk > 0n) {
      if (kk & 1n) {
        if (rx === null) { rx=qx; ry=qy; }
        else {
          var lam = ((qy-ry)*modInv(qx-rx,P))%P; lam=(lam+P)%P;
          var x3=(lam*lam-rx-qx)%P; x3=(x3+P)%P;
          var y3=(lam*(rx-x3)-ry)%P; y3=(y3+P)%P;
          rx=x3; ry=y3;
        }
      }
      var lam2=((3n*qx*qx)*modInv(2n*qy,P))%P; lam2=(lam2+P)%P;
      var x4=(lam2*lam2-2n*qx)%P; x4=(x4+P)%P;
      var y4=(lam2*(qx-x4)-qy)%P; y4=(y4+P)%P;
      qx=x4; qy=y4; kk >>= 1n;
    }
    return {x:rx, y:ry};
  }
  function bigToBytes32(n) {
    var h = n.toString(16).padStart(64, "0");
    return hexToBytes(h);
  }

  // ------------------------------------------------------------------ base58
  var B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";
  function base58Encode(raw) {
    var n = 0n;
    for (var i=0;i<raw.length;i++) n = (n<<8n) + BigInt(raw[i]);
    var out = "";
    while (n > 0n) { var r = n % 58n; n = n / 58n; out = B58[Number(r)] + out; }
    for (i=0;i<raw.length && raw[i]===0;i++) out = "1" + out;
    return out;
  }

  // ------------------------------------------------------------------- BIP39
  function entropyToMnemonic(entropy) {
    if (entropy.length !== 32) throw new Error("entropy must be 32 bytes");
    var hash = sha256(entropy);
    var bits = "";
    for (var i=0;i<32;i++) bits += entropy[i].toString(2).padStart(8,"0");
    bits += hash[0].toString(2).padStart(8,"0"); // first 8 bits = checksum
    var words = [];
    for (i=0;i<24;i++) words.push(WORDLIST[parseInt(bits.substr(i*11,11),2)]);
    return words;
  }
  function mnemonicToEntropy(words) {
    if (!Array.isArray(words)) words = words.trim().toLowerCase().split(/\s+/);
    if (words.length !== 24) throw new Error("need exactly 24 words");
    var bits = "";
    for (var i=0;i<24;i++) {
      var idx = WORDLIST.indexOf(words[i]);
      if (idx < 0) throw new Error("unknown word: "+words[i]);
      bits += idx.toString(2).padStart(11,"0");
    }
    var entBits = bits.substr(0,256), chkBits = bits.substr(256,8);
    var entropy = new Uint8Array(32);
    for (i=0;i<32;i++) entropy[i]=parseInt(entBits.substr(i*8,8),2);
    var hash = sha256(entropy);
    if (hash[0].toString(2).padStart(8,"0") !== chkBits) throw new Error("bad checksum");
    return entropy;
  }

  // ------------------------------------------------------------------ wallet
  function privateKeyToAddress(privHex) {
    var k = BigInt("0x"+privHex);
    var pt = secp256k1Mul(k);
    var xBytes = bigToBytes32(pt.x);
    var prefix = (pt.y & 1n) ? 0x03 : 0x02;
    var pub = concat(new Uint8Array([prefix]), xBytes);
    var h160 = ripemd160(sha256(pub));
    var payload = concat(new Uint8Array([0x3A]), h160);
    var chk = sha256(sha256(payload)).slice(0,4);
    return base58Encode(concat(payload, chk));
  }
  function generateWallet() {
    var entropy = new Uint8Array(32);
    if (global.crypto && global.crypto.getRandomValues) global.crypto.getRandomValues(entropy);
    else for (var i=0;i<32;i++) entropy[i]=Math.floor(Math.random()*256);
    var words = entropyToMnemonic(entropy);
    var privHex = bytesToHex(entropy);
    return { phrase: words.join(" "), address: privateKeyToAddress(privHex), privateKeyHex: privHex };
  }
  function walletFromPhrase(phrase) {
    var entropy = mnemonicToEntropy(phrase);
    var privHex = bytesToHex(entropy);
    return { phrase: phrase.trim().toLowerCase().split(/\s+/).join(" "), address: privateKeyToAddress(privHex), privateKeyHex: privHex };
  }

  global.QuasarWallet = {
    generateWallet: generateWallet,
    walletFromPhrase: walletFromPhrase,
    privateKeyToAddress: privateKeyToAddress,
    entropyToMnemonic: entropyToMnemonic,
    mnemonicToEntropy: mnemonicToEntropy,
    sha256: sha256, ripemd160: ripemd160,
    WORD_COUNT: function(){ return WORDLIST.length; }
  };
})(typeof window !== "undefined" ? window : globalThis);
