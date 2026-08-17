/* =========================================================
   GLOBAL STATE  (ต้องอยู่บนสุดเสมอ)
========================================================= */

let isTyping = false;

let chats;
try{
  const raw=localStorage.getItem(CONFIG.STORE_KEY);
  chats=raw?JSON.parse(raw):{};
}catch(e){
  console.warn("RESET corrupted chat store");
  chats={};
  localStorage.removeItem(CONFIG.STORE_KEY);
}

let currentChatId=localStorage.getItem(CONFIG.CURRENT_KEY);

// =======================
// FLOW STATE (เพิ่ม)
// =======================
let currentFlow = localStorage.getItem("CURRENT_FLOW") || "oee";

function setFlow(flow){
  currentFlow = flow;
  localStorage.setItem("CURRENT_FLOW", flow);
}

function saveAll(){
  localStorage.setItem(CONFIG.STORE_KEY,JSON.stringify(chats));
  localStorage.setItem(CONFIG.CURRENT_KEY,currentChatId);
}

function uuid(){
  return "chat-"+Math.random().toString(36).slice(2,9);
}

if(!currentChatId||!chats[currentChatId]){
  currentChatId=uuid();
  chats[currentChatId]={title:"New chat",messages:[],pin:false};
  saveAll();
}

/* =========================================================
   DOM READY
========================================================= */

document.addEventListener("DOMContentLoaded",()=>{

const chatEl=document.getElementById("chat");
const chatListEl=document.getElementById("chatList");
const fileInput=document.getElementById("fileInput");
const plusBtn=document.getElementById("plusBtn");
const plusMenu=document.getElementById("plusMenu");
const kmModal=document.getElementById("kmModal");
const kmTree=document.getElementById("kmTree");
const kmSelectedPath=document.getElementById("kmSelectedPath");
const confirmKmUpload=document.getElementById("confirmKmUpload");
const cancelKmUpload=document.getElementById("cancelKmUpload");

let pendingKmFiles=[];
let selectedKmPath="";
let uploadInProgress=false;
// KM folder modal is reused for two purposes: 'upload' (pick destination) and
// 'ask' (pick a folder to scope Ask-KM retrieval).
let kmModalMode="upload";
// Folder that Ask-KM queries are scoped to (persisted). Empty = whole vault.
let askKmFolder=localStorage.getItem("ASK_KM_FOLDER")||"";

// Reflect the current flow (and Ask-KM folder) in the indicator above the input.
function updateModeIndicator(){
  const el=document.getElementById("modeIndicator");
  if(!el) return;
  let label;
  switch(currentFlow){
    case "alarm": label="🚨 ALARM"; break;
    case "oee":   label="🔧 OEE"; break;
    case "km":    label=askKmFolder?`📚 ถาม KM — ${askKmFolder}`:"📚 ถาม KM — ทุกโฟลเดอร์"; break;
    default:      label="💬 ทั่วไป";
  }
  el.textContent="ตอนนี้อยู่โหมด: "+label;
}

/* =========================================================
   STATUS TOASTS  (loading / success / error)
========================================================= */

function ensureToastWrap(){
  let w = document.getElementById("toastWrap");
  if(!w){
    w = document.createElement("div");
    w.id = "toastWrap";
    w.className = "toast-wrap";
    document.body.appendChild(w);
  }
  return w;
}

// Returns a handle whose .set(type,msg) swaps the toast between
// loading / success / error. loading stays until updated; success/error
// auto-dismiss. Use one handle per operation so the loading toast becomes
// the result toast in place.
function createToast(){
  const el = document.createElement("div");
  el.className = "toast loading";
  el.innerHTML = `<span class="toast-visual toast-spinner"></span>`+
                 `<div class="toast-body">`+
                   `<div class="toast-msg"></div>`+
                   `<div class="toast-progress"><div class="toast-progress-bar"></div></div>`+
                 `</div>`+
                 `<button class="toast-close" title="ปิด">×</button>`;
  ensureToastWrap().appendChild(el);

  const prog = el.querySelector(".toast-progress");
  const bar = el.querySelector(".toast-progress-bar");
  let timer = null;
  function setWidth(fraction){ bar.style.width = (Math.max(0, Math.min(1, fraction)) * 100).toFixed(1) + "%"; }
  function remove(){ clearTimeout(timer); el.remove(); }
  el.querySelector(".toast-close").onclick = remove;

  function set(type, message, opts){
    opts = opts || {};
    clearTimeout(timer);
    el.className = "toast " + type;
    prog.style.display = "none"; // bar only relevant while loading w/ progress
    const visual = el.querySelector(".toast-visual");
    if(type === "loading"){
      visual.className = "toast-visual toast-spinner";
      visual.textContent = "";
    } else {
      visual.className = "toast-visual toast-icon";
      visual.textContent = type === "success" ? "✅" : "❌";
    }
    el.querySelector(".toast-msg").textContent = message;
    const autoClose = opts.autoClose != null
      ? opts.autoClose
      : (type === "loading" ? 0 : 4000);
    if(autoClose) timer = setTimeout(remove, autoClose);
  }

  // Snap the progress bar to an exact fraction (0..1) and optionally the label.
  // Uses a short transition so a real milestone lands quickly.
  function setBar(fraction, label){
    prog.style.display = "block";
    bar.style.transition = "width .3s ease";
    setWidth(fraction);
    if(label != null) el.querySelector(".toast-msg").textContent = label;
  }

  // Slowly ease the bar toward `target` (0..1) over `seconds` via a long CSS
  // transition — used while a unit of work is in progress so the bar keeps
  // moving instead of sitting still. setBar() then snaps it on completion.
  // Stops just shy of target so it never visually "finishes" early.
  function creepTo(target, label, seconds){
    prog.style.display = "block";
    if(label != null) el.querySelector(".toast-msg").textContent = label;
    const ceiling = Math.max(0, Math.min(1, target) - 0.02);
    bar.style.transition = `width ${seconds || 8}s ease-out`;
    // Force a reflow so the browser registers the new (long) transition before
    // we change the width, otherwise it reuses the previous short transition.
    void bar.offsetWidth;
    setWidth(ceiling);
  }

  return { set, setBar, creepTo, remove, el };
}

// POST JSON and read an NDJSON progress stream. Calls onProgress for each
// {type:'progress'} line and returns the final {type:'done'} object.
async function postStream(url, payload, onProgress){
  return readNdjsonStream(await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  }), onProgress);
}

// Same as postStream but sends a FormData body (for multipart uploads). fetch
// can't report byte-level upload progress, so progress here is file-level
// (driven by the server's {type:'progress'} lines).
async function postStreamForm(url, formData, onProgress){
  return readNdjsonStream(await fetch(url, { method: "POST", body: formData }), onProgress);
}

// Read an NDJSON response body, invoking onProgress per {type:'progress'} line
// and returning the final {type:'done'} object.
async function readNdjsonStream(res, onProgress){
  if(!res.ok || !res.body) throw new Error("Request failed (" + res.status + ")");
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  let final = null;
  while(true){
    const { done, value } = await reader.read();
    if(done) break;
    buf += decoder.decode(value, { stream: true });
    let idx;
    while((idx = buf.indexOf("\n")) >= 0){
      const line = buf.slice(0, idx).trim();
      buf = buf.slice(idx + 1);
      if(!line) continue;
      let msg;
      try { msg = JSON.parse(line); } catch { continue; }
      if(msg.type === "progress" && typeof onProgress === "function") onProgress(msg);
      else if(msg.type === "done") final = msg;
    }
  }
  return final;
}

// Toggle a button into a busy state (spinner + disabled) and back.
function setBtnBusy(btn, busy, busyText){
  if(!btn) return;
  if(busy){
    if(!btn.dataset.label) btn.dataset.label = btn.textContent;
    btn.disabled = true;
    btn.innerHTML = `<span class="btn-spinner"></span>${busyText || btn.dataset.label}`;
  } else {
    btn.disabled = false;
    if(btn.dataset.label) btn.textContent = btn.dataset.label;
  }
}

/* =========================================================
   CHAT ACTIONS
========================================================= */

function handleChatAction(action, chatId){
  if(!chats[chatId]) return;

  switch(action){

    case "rename":{
      const t=prompt("Rename chat",chats[chatId].title);
      if(t){
        chats[chatId].title=t;
        saveAll();
        renderSidebar();
      }
      break;
    }

    case "delete":{
      if(confirm("Delete chat?")){
        delete chats[chatId];
        if(currentChatId===chatId) createNewChat();
        saveAll();
        renderSidebar();
        renderChat();
      }
      break;
    }

    case "pin":{
      chats[chatId].pin=!chats[chatId].pin;
      saveAll();
      renderSidebar();
      break;
    }
  }
}

function createNewChat(){
  const id=uuid();
  chats[id]={title:"New chat",messages:[],pin:false};
  currentChatId=id;
  saveAll();
  renderSidebar();
  renderChat();
}

function addMsg(text,role){
  chats[currentChatId].messages.push({text,role,ts:Date.now()});

  if(chats[currentChatId].messages.length===1)
    chats[currentChatId].title=text.slice(0,25);

  saveAll();
  renderSidebar();
  renderChat();
}

/* =========================================================
   RENDER
========================================================= */

function renderChat(){
  chatEl.innerHTML="";

  chats[currentChatId].messages.forEach((m,i)=>{
    const d=document.createElement("div");
    d.className="msg "+m.role;
    d.id="msg-"+i;
    d.innerHTML=m.text.replace(/\n/g,"<br>");
    chatEl.appendChild(d);
  });

  renderHistory();

  if(isTyping){
    const typing=document.createElement("div");
    typing.className="msg bot";
    typing.innerHTML=`
      <div class="typingBubble">
        <div class="typingSpinner"></div>
        🤖 กำลังคิด...
      </div>
    `;
    chatEl.appendChild(typing);
  }

  chatEl.scrollTop=chatEl.scrollHeight;
}

/* Question history (right panel): list the user's questions in the current
   chat; clicking one scrolls to that message in the chat and flashes it. */
function renderHistory(){
  const listEl=document.getElementById("historyList");
  if(!listEl) return;
  listEl.innerHTML="";
  const msgs=chats[currentChatId].messages;
  msgs.forEach((m,i)=>{
    if(m.role!=="user") return;
    const item=document.createElement("div");
    item.className="history-item";

    const t=m.ts?new Date(m.ts):null;
    const time=document.createElement("span");
    time.className="history-time";
    time.textContent=t?String(t.getHours()).padStart(2,"0")+":"+String(t.getMinutes()).padStart(2,"0"):"";

    const q=document.createElement("span");
    q.className="history-q";
    q.textContent=m.text;

    item.appendChild(time);
    item.appendChild(q);
    item.title=m.text;
    item.onclick=()=>{
      const target=document.getElementById("msg-"+i);
      if(!target) return;
      target.scrollIntoView({behavior:"smooth",block:"center"});
      target.classList.add("msg-highlight");
      setTimeout(()=>target.classList.remove("msg-highlight"),1600);
    };
    listEl.appendChild(item);
  });
  if(!listEl.children.length){
    const empty=document.createElement("div");
    empty.className="history-empty";
    empty.textContent="ยังไม่มีคำถาม";
    listEl.appendChild(empty);
  }
}

function renderSidebar(filter=""){
  chatListEl.innerHTML="";

  Object.entries(chats)
    .filter(([_,c])=>(c.title||"").includes(filter))
    .sort((a,b)=>b[1].pin-a[1].pin)
    .forEach(([id,c])=>{
      const d=document.createElement("div");
      d.className="item"+(id===currentChatId?" active":"");
      d.dataset.chatId=id;

      d.innerHTML=`
        <span>${c.pin?"⭐ ":""}${c.title}</span>
        <div class="chat-actions">
          <span data-action="rename">✏️</span>
          <span data-action="pin">⭐</span>
          <span data-action="delete">🗑️</span>
        </div>
      `;

      chatListEl.appendChild(d);
    });
}

/* =========================================================
   REQUEST QUEUE SYSTEM
========================================================= */

let requestQueue=[];
let processingQueue=false;

function enqueueRequest(task){
  requestQueue.push(task);
  processQueue();
}

async function processQueue(){
  if(processingQueue) return;
  processingQueue=true;

  while(requestQueue.length){
    const job=requestQueue.shift();
    await job();
  }

  processingQueue=false;
}

function updateKmSelectionDisplay(){
  kmSelectedPath.textContent = selectedKmPath
    ? `Selected: ${selectedKmPath}`
    : "Selected: None";
}

function clearKmSelection(){
  selectedKmPath = "";
  updateKmSelectionDisplay();
  confirmKmUpload.disabled = true;
  kmTree.querySelectorAll("li.selected").forEach(el=>el.classList.remove("selected"));
}

function renderKmTree(nodes,parentPath="",container=kmTree){
  container.innerHTML = "";
  const list = document.createElement("ul");

  function renderNodes(items, parent, target){
    items.forEach(item=>{
      const path = parent ? `${parent}/${item.name}` : item.name;
      const li = document.createElement("li");
      li.dataset.path = path;
      li.className = "km-folder-item";

      const hasChildren = Array.isArray(item.children) && item.children.length > 0;
      const isLeaf = !hasChildren;
      const toggle = document.createElement("span");
      toggle.className = "toggle";
      toggle.textContent = hasChildren ? "[+]" : "";
      toggle.addEventListener("click", e=>{
        e.stopPropagation();
        const nested = li.querySelector("ul");
        if(!nested) return;
        const expanded = nested.style.display !== "none";
        nested.style.display = expanded ? "none" : "block";
        toggle.textContent = expanded ? "[+]" : "[-]";
      });

      const label = document.createElement("span");
      label.textContent = item.name;
      label.style.paddingLeft = hasChildren ? "0" : "18px";
      label.style.cursor = (isLeaf || kmModalMode === "ask") ? "pointer" : "default";

      li.dataset.leaf = isLeaf ? "true" : "false";
      li.appendChild(toggle);
      li.appendChild(label);
      li.addEventListener("click", (e)=>{
        // Nested <li> elements bubble clicks to their parent folder; stop here
        // so clicking a child doesn't also re-select its ancestor.
        e.stopPropagation();
        // Upload mode: only leaf (machine) folders are valid targets.
        // Ask mode: any folder is selectable (scopes retrieval to it + below).
        if(kmModalMode !== "ask" && !isLeaf) return;
        selectedKmPath = path;
        updateKmSelectionDisplay();
        confirmKmUpload.disabled = false;
        kmTree.querySelectorAll("li.selected").forEach(el=>el.classList.remove("selected"));
        li.classList.add("selected");
      });

      target.appendChild(li);

      if(hasChildren){
        const childList = document.createElement("ul");
        childList.style.display = "none";
        renderNodes(item.children, path, childList);
        li.appendChild(childList);
      }
    });
  }

  renderNodes(nodes,parentPath,list);
  container.appendChild(list);
}

async function loadKmFolders(){
  kmTree.innerHTML = "Loading folder tree...";
  try{
    const res = await fetch('/api/km-folders');
    if(!res.ok) throw new Error('Failed to load KM folders');
    const folders = await res.json();
    renderKmTree(folders);
  }catch(e){
    kmTree.innerHTML = "ไม่สามารถโหลดโฟลเดอร์ KM ได้";
  }
}

function openKmModal(files){
  kmModalMode = "upload";
  pendingKmFiles = Array.from(files);
  uploadInProgress = false;
  document.getElementById("kmModalTitle").textContent = "Select KM Destination";
  confirmKmUpload.textContent = "Confirm Upload";
  clearKmSelection();
  loadKmFolders();
  kmModal.classList.remove("hidden");
}

function openAskKmModal(){
  kmModalMode = "ask";
  pendingKmFiles = [];
  uploadInProgress = false;
  document.getElementById("kmModalTitle").textContent = "Select KM Folder to Ask";
  confirmKmUpload.textContent = "Use this folder";
  clearKmSelection();
  loadKmFolders();
  kmModal.classList.remove("hidden");
}

function closeKmModal(){
  kmModal.classList.add("hidden");
  pendingKmFiles = [];
  uploadInProgress = false;
  kmModalMode = "upload";
  clearKmSelection();
}

async function uploadKmFiles(){
  if(uploadInProgress) return;
  if(!pendingKmFiles.length || !selectedKmPath) return;

  uploadInProgress = true;
  setBtnBusy(confirmKmUpload, true, "กำลังอัปโหลด...");

  const fileCount = pendingKmFiles.length;
  const toast = createToast();
  toast.set("loading", `กำลังอัปโหลด (${fileCount} ไฟล์)...`);
  // Start creeping toward the first file's slot so the bar moves immediately
  // (the server takes a moment to convert the first file before reporting).
  toast.creepTo(fileCount ? 1 / fileCount : 1, `กำลังอัปโหลด 0% (0/${fileCount} ไฟล์)`);

  const formData = new FormData();
  pendingKmFiles.forEach(f=>formData.append('data', f));
  formData.append('targetPath', selectedKmPath);
  try{
    // The server streams file-level progress and only closes once every file is
    // fully processed — so the upload UI stays open until conversion is done and
    // KMs can't be trained while still half-converted. Each progress line means
    // `done` files are finished; we snap the bar to done/total, then creep
    // toward the next file's slot so it keeps moving while that file converts.
    const result = await postStreamForm('/api/km/upload', formData, (m)=>{
      if(m.total > 0){
        const pct = Math.round((m.done / m.total) * 100);
        const label = `กำลังอัปโหลด ${pct}% (${m.done}/${m.total} ไฟล์)${m.current ? ' • ' + m.current : ''}`;
        toast.setBar(m.done / m.total, label);
        if(m.done < m.total) toast.creepTo((m.done + 1) / m.total, label);
      } else {
        toast.set("loading", `กำลังอัปโหลด (${fileCount} ไฟล์)...`);
      }
    });
    if(!result || !result.success) throw new Error((result && result.error) || 'Upload failed');
    const n = (result && result.count) || fileCount;
    const ids = result && Array.isArray(result.kms)
      ? result.kms.map(k => k.kmId).join(', ')
      : '';
    toast.set("success", `อัปโหลดสำเร็จ ${n} ไฟล์ (สร้าง ${n} KM) → ${selectedKmPath}`);
    addMsg(`📁 Upload สำเร็จ (${n} ไฟล์ = ${n} KM) to ${selectedKmPath}${ids ? `\nKM_ID: ${ids}` : ''}`,'bot');
  }catch(e){
    toast.set("error", "อัปโหลดล้มเหลว — ลองใหม่อีกครั้ง");
    addMsg('❌ Upload ล้มเหลว','bot');
  } finally {
    uploadInProgress = false;
    setBtnBusy(confirmKmUpload, false);
    closeKmModal();
  }
}

/* =========================================================
   SEND MESSAGE (NO STREAM — STABLE MODE)
========================================================= */

async function sendMessage(){

  const input=document.getElementById("input");
  let text=input.value.trim();
  if(!text) return;

  // =======================
  // FLOW SWITCH (เพิ่ม)
  // =======================
  const lower = text.toLowerCase();

  if(lower.startsWith("zyalarm ")){
    setFlow("alarm");
    text = text.substring(8).trim();
    addMsg("🔀 switched to ALARM mode","bot");
  }
  else if(lower.startsWith("oee ")){
    setFlow("oee");
    text = text.substring(4).trim();
    addMsg("🔀 switched to OEE mode","bot");
  }
  else if(lower.startsWith("km ")){
    setFlow("km");
    text = text.substring(3).trim();
    addMsg("📚 switched to KM mode","bot");
  }
  updateModeIndicator();

  input.value="";
  addMsg(text,"user");

  enqueueRequest(async ()=>{

    const typingId="typing-"+Date.now();

    const typingDiv=document.createElement("div");
    typingDiv.className="msg bot";
    typingDiv.id=typingId;

    typingDiv.innerHTML=`
      <div class="typingBubble">
        <div class="typingSpinner"></div>
        🤖 กำลังคิด...
      </div>
    `;

    chatEl.appendChild(typingDiv);
    chatEl.scrollTop=chatEl.scrollHeight;

    const history=chats[currentChatId].messages
      .map(m=>`${m.role}: ${m.text}`).join("\n");

    try{

      // =======================
      // SELECT ENDPOINT (เพิ่ม)
      // =======================
      let url = CONFIG.N8N_WEBHOOK_URL;

      if(currentFlow === "alarm"){
        url = CONFIG.N8N_ALARM_URL;
      }
      else if(currentFlow === "oee"){
        url = CONFIG.N8N_OEE_URL;
      }
      else if(currentFlow === "km"){
        url = "/api/ask_km";
      }
      
      const res=await fetch(url,{
        method:"POST",
        headers:{ "Content-Type":"application/json" },
        body:JSON.stringify({
          question:text,
          history,
          flow: currentFlow,
          folder: askKmFolder
        })
      });

      if(!res.ok)
        throw new Error("Server error");

      const raw=await res.text();
      if(!raw.trim()){
        document.getElementById(typingId)?.remove();
        addMsg("⚠️ AI ตอบกลับว่าง (n8n ส่ง body ว่าง) — ตรวจ workflow ask_km","bot");
        return;
      }
      let data;
      try{ data=JSON.parse(raw); }
      catch{ data={ text: raw }; }

      document.getElementById(typingId)?.remove();

      const reply=
        data.reply||
        data.text||
        data.output||
        data.result||
        JSON.stringify(data);

      addMsg(reply,"bot");

    }catch(e){

      document.getElementById(typingId)?.remove();
      addMsg("❌ เชื่อมต่อ AI ไม่ได้","bot");

    }

  });
}

/* =========================================================
   EVENTS
========================================================= */

document.getElementById("sendBtn").onclick=sendMessage;
document.getElementById("newChatBtn").onclick=createNewChat;

// Role-aware UI: viewers (read-only) lose all write actions and the logout
// button is replaced by a badge + a login link.
fetch("/api/me").then(r=>r.json()).then(me=>{
  if(me && me.role==="viewer"){
    document.body.classList.add("viewer");
    const logoutBtn=document.getElementById("logoutBtn");
    if(logoutBtn){
      const badge=document.createElement("div");
      badge.className="viewer-badge";
      badge.innerHTML=`👁️ ผู้ชม — <a href="/login.html" style="color:inherit;text-decoration:underline;">เข้าสู่ระบบ</a>`;
      logoutBtn.replaceWith(badge);
    }
  }
}).catch(()=>{});

document.getElementById("input").addEventListener("keydown",e=>{
  if(e.key==="Enter"&&!e.shiftKey){
    e.preventDefault();
    sendMessage();
  }
});

plusBtn.onclick=e=>{
  e.stopPropagation();
  plusMenu.style.display="block";
};
plusMenu.onclick=e=>e.stopPropagation();
document.body.onclick=()=>plusMenu.style.display="none";

document.getElementById("searchInput").oninput=e=>{
  renderSidebar(e.target.value);
};

chatListEl.addEventListener("click",e=>{
  const actionEl=e.target.closest("[data-action]");
  const itemEl=e.target.closest(".item");
  if(!itemEl) return;

  const chatId=itemEl.dataset.chatId;

  if(actionEl){
    e.stopPropagation();
    handleChatAction(actionEl.dataset.action,chatId);
    return;
  }

  currentChatId=chatId;
  saveAll();
  renderSidebar();
  renderChat();
});

/* =========================================================
   UPLOAD
========================================================= */

document.getElementById("plusMenu").addEventListener("click",e=>{
  const uploadType=e.target.dataset.upload;
  if(uploadType){
    fileInput.accept=uploadType==="photo"?"image/*":"";
    fileInput.click();
    return;
  }
  // Train KM menu
  if(e.target.id==="trainKmMenuItem"){
    openTrainKmModal();
    return;
  }
  // Ask KM menu
  if(e.target.id==="askKmMenuItem"){
    openAskKmModal();
    return;
  }
  // Add Summary menu
  if(e.target.id==="addSummaryMenuItem"){
    openAddSummaryModal();
    return;
  }
});

fileInput.addEventListener("change",e=>{
  if(e.target.files.length){
    openKmModal(e.target.files);
    e.target.value="";
  }
});

confirmKmUpload.onclick = () => {
  if(!selectedKmPath) return;

  // Ask-KM mode: remember the folder, switch to KM flow, no upload.
  if(kmModalMode === "ask"){
    askKmFolder = selectedKmPath;
    localStorage.setItem("ASK_KM_FOLDER", askKmFolder);
    setFlow("km");
    updateModeIndicator();
    addMsg(`📚 พร้อมตอบคำถามจากโฟลเดอร์: ${askKmFolder}`,"bot");
    closeKmModal();
    return;
  }

  // Upload mode: only leaf folders are valid destinations.
  if(uploadInProgress) return;
  const selectedNode = kmTree.querySelector(`li[data-path="${selectedKmPath}"]`);
  if(selectedNode && selectedNode.dataset.leaf === 'true'){
    confirmKmUpload.disabled = true;
    uploadKmFiles();
  }
};

cancelKmUpload.onclick = () => {
  closeKmModal();
};

// ============ Train KM Modal ============
const trainKmModal = document.getElementById("trainKmModal");
const trainKmListArea = document.getElementById("trainKmListArea");
const trainSelectedBtn = document.getElementById("trainSelectedBtn");
const cancelTrainKm = document.getElementById("cancelTrainKm");

let trainKmListData = [];

function closeTrainKmModal() {
  trainKmModal.classList.add("hidden");
  trainKmListArea.innerHTML = '';
  trainKmListData = [];
}

async function openTrainKmModal() {
  trainKmModal.classList.remove("hidden");
  trainKmListArea.innerHTML = '<div style="text-align:center; color:#aaa;">Loading...</div>';
  trainSelectedBtn.disabled = true;

  let data = [];
  try {
    const res = await fetch("/api/km/not-trained");
    if(res.ok) data = await res.json();
  } catch(e){ /* ignore */ }

  trainKmListData = data;
  if(!Array.isArray(data) || data.length === 0){
    trainKmListArea.innerHTML = '<div style="color:#aaa; text-align:center; padding:30px 0;">No KM knowledge requires training.</div>';
    return;
  }
  // Table
  let html = '<table class="km-train-table" style="width:100%; border-spacing:0 8px;">'+
    '<thead><tr>'+
    '<th></th>'+
    '<th style="text-align:left">Source File</th>'+
    '<th style="text-align:left">Category/Machine</th>'+
    '<th style="text-align:right">Slide Count</th>'+
    '</tr></thead><tbody>';

  data.forEach((row,i)=>{
    html += `<tr>
      <td style="text-align:center"><input type="checkbox" class="km-train-checkbox" data-idx="${i}"></td>
      <td style="word-break:break-all">${row.sourceFile||''}</td>
      <td>${row.category||''} / ${row.machine||''}</td>
      <td style="text-align:right">${row.slideCount||0}</td>
    </tr>`;
  });
  html += '</tbody></table>';
  trainKmListArea.innerHTML = html;

  // Enable Train Selected only if any checked
  const checkboxes = trainKmListArea.querySelectorAll('.km-train-checkbox');
  function updateTrainBtnState(){
    trainSelectedBtn.disabled = !Array.from(checkboxes).some(cb=>cb.checked);
  }
  checkboxes.forEach(cb=>{
    cb.onchange = updateTrainBtnState;
  });
  updateTrainBtnState();
}

cancelTrainKm.onclick = closeTrainKmModal;
trainSelectedBtn.onclick = async () => {
  const checkboxes = trainKmListArea.querySelectorAll('.km-train-checkbox:checked');
  const idxArr = Array.from(checkboxes).map(cb => Number(cb.dataset.idx));
  if (!idxArr.length) return;

  // Use 'kmId' (verified above)
  const kmIds = idxArr
    .map(idx => trainKmListData[idx]?.kmId)
    .filter(kmId => !!kmId);

  const total = kmIds.length;
  const toast = createToast();
  toast.set("loading", "กำลังเทรน...");
  setBtnBusy(trainSelectedBtn, true, "กำลังเทรน...");
  try {
    const final = await postStream('/api/km/train', { kmIds }, m=>{
      if(m.total > 0){
        const pct = Math.round((m.done / m.total) * 100);
        if(m.done >= m.total){
          // All slides analysed; the server is now writing the summary file.
          // Hold near 100% with a label that says so, instead of looking done.
          toast.setBar(0.99, `เทรน ${pct}% (${m.done}/${m.total} สไลด์) • กำลังสรุป...`);
        } else {
          toast.setBar(m.done / m.total, `เทรน ${pct}% (${m.done}/${m.total} สไลด์)${m.current ? ' • ' + m.current : ''}`);
        }
      } else {
        toast.set("loading", "กำลังเทรน...");
      }
    });
    if (final && final.success) {
      toast.set("success", `เทรนสำเร็จ ${final.updated}/${total} รายการ`);
      setBtnBusy(trainSelectedBtn, false);
      await openTrainKmModal(); // Refresh KM list after success
      closeTrainKmModal();
    } else {
      toast.set("error", "เทรนไม่สำเร็จ: " + ((final && final.error) || 'Unknown error'));
      setBtnBusy(trainSelectedBtn, false);
    }
  } catch (e) {
    toast.set("error", "เทรนไม่สำเร็จ: " + e.message);
    setBtnBusy(trainSelectedBtn, false);
  }
};

// ============ Engineering Extraction Review (draft-only) ============
const engineeringReviewModal = document.getElementById("engineeringReviewModal");
const engineeringReviewList = document.getElementById("engineeringReviewList");
const engineeringReviewDraft = document.getElementById("engineeringReviewDraft");
let engineeringWorkflow={extractionRunId:null,review:null,decisions:new Map(),commands:[]};
document.getElementById("reviewEngineeringMenuItem").onclick = openEngineeringReview;
document.getElementById("closeEngineeringReview").onclick = () => engineeringReviewModal.classList.add("hidden");

async function openEngineeringReview(){
  engineeringReviewModal.classList.remove("hidden"); engineeringReviewDraft.classList.add("hidden");
  engineeringReviewList.replaceChildren();
  const loading=document.createElement("p"); loading.textContent="Loading trained documents..."; engineeringReviewList.append(loading);
  try{
    const response=await fetch("/api/km/trained"); const documents=await response.json(); engineeringReviewList.replaceChildren();
    if(!Array.isArray(documents)||!documents.length){ const empty=document.createElement("p"); empty.textContent="No successfully trained documents are available."; engineeringReviewList.append(empty); return; }
    documents.forEach(documentInfo=>{ const row=document.createElement("div"); row.className="engineering-review-row";
      const text=document.createElement("span"); text.textContent=`${documentInfo.sourceFile} (${documentInfo.kmId})`;
      const button=document.createElement("button"); button.type="button"; button.textContent="Extract / Review Draft"; button.onclick=()=>loadEngineeringDraft(documentInfo.kmId); row.append(text,button); engineeringReviewList.append(row); });
  }catch(_error){ loading.textContent="Unable to load trained documents."; }
}

async function loadEngineeringDraft(kmId){
  engineeringReviewDraft.classList.remove("hidden"); engineeringReviewDraft.replaceChildren();
  const loading=document.createElement("p"); loading.textContent="Creating draft extraction..."; engineeringReviewDraft.append(loading);
  try{
    const response=await fetch("/api/km/extraction-draft",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({kmId})}); const data=await response.json();
    if(!data.success) throw new Error(data.error||"Extraction failed"); engineeringWorkflow={extractionRunId:data.extraction_run_id,review:null,decisions:new Map(),commands:[]}; renderEngineeringDraft(data.draft);
  }catch(error){ loading.textContent=`Extraction failed safely: ${error.message}`; }
}

function engineeringSection(parent,title){ const section=document.createElement("section"); section.className="engineering-review-section"; const heading=document.createElement("h4"); heading.textContent=title; section.append(heading); parent.append(section); return section; }
function renderExtractedFields(parent,fields){ Object.entries(fields||{}).forEach(([name,item])=>{ const row=document.createElement("div"); row.className="engineering-review-row";
  const label=document.createElement("strong"); label.textContent=`EXTRACTED ${name.replaceAll("_"," ")}: `; const value=document.createElement("span"); value.textContent=String(item.value??"");
  const confidence=document.createElement("span"); confidence.className="engineering-badge"; confidence.textContent=` confidence ${Math.round((item.confidence||0)*100)}%`; row.append(label,value,confidence);
  (item.evidence||[]).forEach(evidence=>{ const note=document.createElement("span"); note.className="engineering-evidence"; note.textContent=`Evidence: ${evidence.artifact} · ${evidence.location}${evidence.excerpt?` · ${evidence.excerpt}`:""}`; row.append(note); }); parent.append(row); }); }
function renderCandidates(parent,candidates,onSelect,targetRef="candidate",kind="equipment_part"){ const heading=document.createElement("strong"); heading.textContent="CANDIDATES"; parent.append(heading);
  if(!candidates?.length){ const empty=document.createElement("p"); empty.textContent="No canonical candidate returned; no identity was selected."; parent.append(empty); return; }
  const group=`candidate-${crypto.randomUUID()}`; candidates.forEach(candidate=>{ const row=document.createElement("label"); row.className="engineering-candidate"; const radio=document.createElement("input"); radio.type="radio"; radio.name=group;
    const text=document.createElement("span"); text.textContent=`${candidate.canonical_id} · ${candidate.metadata.display_name||candidate.metadata.supplier_name||candidate.metadata.contact_name||""} · ${(candidate.match_evidence||[]).map(e=>e.signal).join(", ")}`;
    radio.onchange=()=>{ text.dataset.state="confirmed-draft"; text.textContent=`REVIEWER DECISION: use ${candidate.canonical_id}`; engineeringWorkflow.decisions.set(targetRef,{target_ref:targetRef,kind,action:"use_existing",canonical_id:candidate.canonical_id,expected_canonical_version:String(candidate.metadata.supplier_canonical_revision??candidate.metadata.canonical_revision??"")||null}); if(onSelect)onSelect(candidate.canonical_id); }; row.append(radio,text); parent.append(row); });
  const propose=document.createElement("button");propose.type="button";propose.textContent="Propose New";propose.onclick=()=>engineeringWorkflow.decisions.set(targetRef,{target_ref:targetRef,kind,action:"propose_new"});
  const ignore=document.createElement("button");ignore.type="button";ignore.textContent=kind.includes("equipment_part")?"Not Equipment / Part":"Ignore";ignore.onclick=()=>engineeringWorkflow.decisions.set(targetRef,{target_ref:targetRef,kind,action:kind.includes("equipment_part")?"not_equipment_part":"ignore"});parent.append(propose,ignore); }

function renderEngineeringDraft(draft){ engineeringReviewDraft.replaceChildren();
  const source=engineeringSection(engineeringReviewDraft,"Source and Classification"); const sourceText=document.createElement("p"); sourceText.textContent=`${draft.source_file} · ${draft.source_document_id} · SHA-256 ${draft.source_content_sha256} · ${draft.extractor_version} / ${draft.schema_version}`; source.append(sourceText);
  const classification=document.createElement("p"); classification.textContent=`EXTRACTED ${draft.classification.document_type} · confidence ${Math.round(draft.classification.confidence*100)}% · ${draft.classification.reason}`; source.append(classification);
  (draft.classification.evidence||[]).forEach(e=>{const note=document.createElement("span");note.className="engineering-evidence";note.textContent=`Evidence: ${e.artifact} · ${e.location} · ${e.excerpt||""}`;source.append(note);});
  if(draft.quotation){ const quote=engineeringSection(engineeringReviewDraft,"Quotation"); renderExtractedFields(quote,draft.quotation.fields);
    if(draft.quotation.issuer_supplier){ const supplier=engineeringSection(engineeringReviewDraft,"Issuer / Supplier (not Customer)"); renderExtractedFields(supplier,draft.quotation.issuer_supplier.fields); renderCandidates(supplier,draft.quotation.issuer_supplier.candidates,(supplierId)=>loadDraftContactCandidates(draft.quotation.supplier_contacts,supplierId),"supplier","supplier"); }
    const buyer=engineeringSection(engineeringReviewDraft,"Customer / Buyer"); renderExtractedFields(buyer,draft.quotation.customer_buyer);
    const contacts=engineeringSection(engineeringReviewDraft,"Supplier Contact Drafts"); contacts.id="engineeringContactDrafts"; draft.quotation.supplier_contacts.forEach(contact=>{ const item=engineeringSection(contacts,contact.draft_id); renderExtractedFields(item,contact.fields); });
    const lines=engineeringSection(engineeringReviewDraft,"Quotation Lines"); draft.quotation.lines.forEach(line=>{const item=engineeringSection(lines,`${line.draft_id} · ${line.line_type}`);renderExtractedFields(item,line.fields);if(line.equipment_part)renderCandidates(item,line.equipment_part.candidates,null,line.equipment_part.draft_id,"equipment_part");}); }
  if(draft.manual){ const manual=engineeringSection(engineeringReviewDraft,"Manual"); renderExtractedFields(manual,draft.manual.fields); if(draft.manual.equipment_part)renderCandidates(manual,draft.manual.equipment_part.candidates,null,draft.manual.equipment_part.draft_id,"manual_equipment_part"); }
  (draft.integration_errors||[]).forEach(error=>{const warning=document.createElement("p");warning.textContent=`Canonical lookup unavailable: ${error}`;engineeringReviewDraft.append(warning);}); appendEngineeringWorkflowControls(engineeringReviewDraft);
}

async function loadDraftContactCandidates(contacts,supplierResourceId){
  for(const contact of contacts||[]){ try{ const response=await fetch("/api/km/extraction-contact-candidates",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({supplierResourceId,fields:contact.fields})}); const data=await response.json(); if(data.success)contact.candidates=(data.candidates||[]).map(item=>({canonical_id:item.contact_id,metadata:item,match_evidence:item.match_evidence||[]})); }catch(_error){ /* Provisional Supplier choice remains usable. */ } }
  const area=document.getElementById("engineeringContactDrafts"); if(area){ area.replaceChildren(); const heading=document.createElement("h4"); heading.textContent="Supplier Contact Drafts"; area.append(heading); contacts.forEach(contact=>{const item=engineeringSection(area,contact.draft_id);renderExtractedFields(item,contact.fields);renderCandidates(item,contact.candidates,null,contact.draft_id,"contact");}); }
}

function appendEngineeringWorkflowControls(parent){const section=engineeringSection(parent,"Persistent Review Workflow");const tag=document.createElement("input");tag.placeholder="Optional explicit KepwarePath (no automatic inference)";tag.id="engineeringKepwarePath";const save=document.createElement("button");save.type="button";save.textContent="Save Review Draft";save.onclick=saveEngineeringReview;const confirmButton=document.createElement("button");confirmButton.type="button";confirmButton.textContent="Confirm Review";confirmButton.onclick=confirmEngineeringReview;const cancel=document.createElement("button");cancel.type="button";cancel.textContent="Cancel Review";cancel.onclick=cancelEngineeringReview;const notice=document.createElement("p");notice.id="engineeringCommandNotice";notice.textContent="Confirmed means READY commands only. Nothing is written to OpcTagManager.";section.append(tag,save,confirmButton,cancel,notice);}
async function ensureEngineeringReview(){if(engineeringWorkflow.review)return;const response=await fetch(`/api/engineering/extractions/${encodeURIComponent(engineeringWorkflow.extractionRunId)}/reviews`,{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});const data=await response.json();if(!data.success)throw new Error(data.error);engineeringWorkflow.review=data.review;}
async function saveEngineeringReview(){try{await ensureEngineeringReview();const path=document.getElementById("engineeringKepwarePath")?.value.trim();const response=await fetch(`/api/engineering/reviews/${encodeURIComponent(engineeringWorkflow.review.review_id)}`,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({concurrency_token:engineeringWorkflow.review.concurrency_token,decisions:[...engineeringWorkflow.decisions.values()],intended_kepware_paths:path?[path]:[]})});const data=await response.json();if(!data.success)throw new Error(data.error);engineeringWorkflow.review=data.review;document.getElementById("engineeringCommandNotice").textContent="Review draft saved with optimistic concurrency.";return true;}catch(error){document.getElementById("engineeringCommandNotice").textContent=`Save failed: ${error.message}`;return false;}}
async function confirmEngineeringReview(){if(!await saveEngineeringReview()||!engineeringWorkflow.review)return;const response=await fetch(`/api/engineering/reviews/${encodeURIComponent(engineeringWorkflow.review.review_id)}/confirm`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({concurrency_token:engineeringWorkflow.review.concurrency_token})});const data=await response.json();if(!data.success)return document.getElementById("engineeringCommandNotice").textContent=`Confirm failed: ${data.error}`;engineeringWorkflow.review=data.review;engineeringWorkflow.commands=data.review.commands||[];renderConfirmedCommands();}
async function cancelEngineeringReview(){if(!engineeringWorkflow.review)return;const response=await fetch(`/api/engineering/reviews/${encodeURIComponent(engineeringWorkflow.review.review_id)}/cancel`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({concurrency_token:engineeringWorkflow.review.concurrency_token})});const data=await response.json();if(data.success){engineeringWorkflow.review=data.review;document.getElementById("engineeringCommandNotice").textContent="Review cancelled.";}}
function renderConfirmedCommands(){const section=engineeringSection(engineeringReviewDraft,"Canonical Execution");engineeringWorkflow.commands.forEach(command=>{const row=document.createElement("div");row.className="engineering-review-row";const blocked=command.command_type.startsWith("ProposeCreate")||command.command_type.startsWith("ProposeUpdate");row.textContent=`${blocked?"BLOCKED":command.status.toUpperCase()} · ${command.command_type}${blocked?" · Requires future master-data approval phase":""}`;section.append(row);});engineeringReviewDraft.querySelectorAll("input,button").forEach(control=>control.disabled=true);const dry=document.createElement("button");dry.type="button";dry.textContent="Dry Run";dry.disabled=false;dry.onclick=()=>runCanonicalExecution(true,section);const execute=document.createElement("button");execute.type="button";execute.textContent="Execute Canonical Changes";execute.disabled=true;execute.id="engineeringExecuteCanonical";execute.onclick=()=>runCanonicalExecution(false,section);const warning=document.createElement("p");warning.textContent="Review Confirmed is separate from Canonical Changes Executed.";section.append(dry,execute,warning);}
async function runCanonicalExecution(dryRun,section){const suffix=dryRun?"/dry-run":"";const response=await fetch(`/api/engineering/reviews/${encodeURIComponent(engineeringWorkflow.review.review_id)}/execution${suffix}`,{method:"POST"});const data=await response.json();const old=section.querySelector(".engineering-execution-result");if(old)old.remove();const output=document.createElement("pre");output.className="engineering-execution-result";output.textContent=data.success?JSON.stringify(data.execution.results||data.execution.commands,null,2):`Execution unavailable: ${data.error}`;section.append(output);const execute=document.getElementById("engineeringExecuteCanonical");if(dryRun&&data.success)execute.disabled=!(data.execution.clean&&data.execution.write_enabled);}


// ============ Add Summary Modal ============
const addSummaryModal = document.getElementById("addSummaryModal");
const addSummaryListArea = document.getElementById("addSummaryListArea");
const generateSummaryBtn = document.getElementById("generateSummaryBtn");
const cancelAddSummary = document.getElementById("cancelAddSummary");

let addSummaryListData = [];

function closeAddSummaryModal(){
  addSummaryModal.classList.add("hidden");
  addSummaryListArea.innerHTML = '';
  addSummaryListData = [];
}

async function openAddSummaryModal(){
  addSummaryModal.classList.remove("hidden");
  addSummaryListArea.innerHTML = '<div style="text-align:center; color:#aaa;">Loading...</div>';
  generateSummaryBtn.disabled = true;

  let data = [];
  try {
    const res = await fetch("/api/km/trained-list");
    if(res.ok) data = await res.json();
  } catch(e){ /* ignore */ }

  addSummaryListData = data;
  if(!Array.isArray(data) || data.length === 0){
    addSummaryListArea.innerHTML = '<div style="color:#aaa; text-align:center; padding:30px 0;">ยังไม่มี KM ที่เทรนแล้ว</div>';
    return;
  }

  let html = '<table class="km-train-table" style="width:100%; border-spacing:0 8px;">'+
    '<thead><tr>'+
    '<th></th>'+
    '<th style="text-align:left">Source File</th>'+
    '<th style="text-align:left">Category/Machine</th>'+
    '<th style="text-align:center">Summary</th>'+
    '</tr></thead><tbody>';

  data.forEach((row,i)=>{
    const summaryTag = row.hasSummary
      ? '<span style="color:#7CFC9B">✔ มีแล้ว</span>'
      : '<span style="color:#aaa">—</span>';
    html += `<tr>
      <td style="text-align:center"><input type="checkbox" class="km-summary-checkbox" data-idx="${i}"></td>
      <td style="word-break:break-all">${row.sourceFile||''}</td>
      <td>${row.category||''} / ${row.machine||''}</td>
      <td style="text-align:center">${summaryTag}</td>
    </tr>`;
  });
  html += '</tbody></table>';
  addSummaryListArea.innerHTML = html;

  const checkboxes = addSummaryListArea.querySelectorAll('.km-summary-checkbox');
  function updateBtnState(){
    generateSummaryBtn.disabled = !Array.from(checkboxes).some(cb=>cb.checked);
  }
  checkboxes.forEach(cb=>{ cb.onchange = updateBtnState; });
  updateBtnState();
}

cancelAddSummary.onclick = closeAddSummaryModal;
generateSummaryBtn.onclick = async () => {
  const checkboxes = addSummaryListArea.querySelectorAll('.km-summary-checkbox:checked');
  const idxArr = Array.from(checkboxes).map(cb => Number(cb.dataset.idx));
  if (!idxArr.length) return;
  const kmIds = idxArr.map(idx => addSummaryListData[idx]?.kmId).filter(kmId => !!kmId);

  const total = kmIds.length;
  const toast = createToast();
  toast.set("loading", `กำลังสร้าง summary 0/${total}...`);
  toast.setBar(0, `สร้าง summary 0/${total}`);
  setBtnBusy(generateSummaryBtn, true, "กำลังสร้าง...");
  try {
    const final = await postStream('/api/km/summarize', { kmIds }, m=>{
      toast.setBar(m.done / m.total, `สร้าง summary ${m.done}/${m.total}${m.current ? ' • ' + m.current : ''}`);
    });
    if (final && final.success) {
      toast.set("success", `สร้าง summary สำเร็จ ${final.updated}/${total} ไฟล์`);
      setBtnBusy(generateSummaryBtn, false);
      await openAddSummaryModal(); // refresh list
    } else {
      toast.set("error", "สร้าง summary ไม่สำเร็จ: " + ((final && final.error) || 'Unknown error'));
      setBtnBusy(generateSummaryBtn, false);
    }
  } catch (e) {
    toast.set("error", "สร้าง summary ไม่สำเร็จ: " + e.message);
    setBtnBusy(generateSummaryBtn, false);
  }
};

/* =========================================================
   INIT
========================================================= */

renderSidebar();
renderChat();
updateModeIndicator();

});

