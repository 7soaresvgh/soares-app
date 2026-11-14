const API_BASE = "https://soares-reserva-ai-heloysa.onrender.com";
const $ = id => document.getElementById(id);
let token = localStorage.getItem("sra_token") || "";
let me = null, authMode = "login", currentView = "chat", isPlaying = false;
const headers = () => ({ "Content-Type":"application/json", ...(token ? {Authorization:`Bearer ${token}`} : {}) });
function apiErrorMessage(detail, fallback="Erro na solicitação.") {
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const messages = detail.map(item => {
      if (typeof item === "string") return item;
      const where = Array.isArray(item?.loc) ? item.loc.filter(x => x !== "body").join(" → ") : "";
      const msg = typeof item?.msg === "string" ? item.msg : "";
      return [where, msg].filter(Boolean).join(": ");
    }).filter(Boolean);
    if (messages.length) return messages.join(" · ");
  }
  if (detail && typeof detail === "object") {
    for (const key of ["message", "msg", "error", "description"]) {
      if (typeof detail[key] === "string" && detail[key].trim()) return detail[key];
    }
    try { return JSON.stringify(detail); } catch {}
  }
  return fallback;
}
async function api(path, opts={}) {
  const r = await fetch(API_BASE+path, { ...opts, headers:{...headers(), ...(opts.headers||{})} });
  const data = await r.json().catch(()=>({detail:"Resposta inválida do servidor."}));
  if (!r.ok) {
    if (path === "/auth/login" && (r.status === 401 || r.status === 422)) throw new Error("Senha ou usuário incorreto");
    throw new Error(apiErrorMessage(data?.detail ?? data?.error ?? data, "Erro na solicitação."));
  }
  return data;
}
function toast(s){$("toast").textContent=s;$("toast").classList.add("show");setTimeout(()=>$("toast").classList.remove("show"),2600)}
function showAuth(){ $("auth").classList.remove("hidden");$("app").classList.add("hidden"); }
function showApp(){ $("auth").classList.add("hidden");$("app").classList.remove("hidden");$("profile-name").textContent=me.name;$("welcome-name").textContent=me.name;if($("profile-username"))$("profile-username").value=me.username?"@"+me.username:"";applyProfile(); }
function setMode(mode){authMode=mode;document.querySelectorAll(".tab").forEach(b=>b.classList.toggle("active",b.dataset.tab===mode));$("name-field").classList.toggle("hidden",mode!=="register");$("username-field").classList.toggle("hidden",mode!=="register");$("email").type=mode==="login"?"text":"email";$("email").setAttribute("autocomplete",mode==="login"?"username":"email");document.querySelector('label[for="email"]').textContent=mode==="login"?"Usuário ou e-mail":"E-mail";$("email").placeholder=mode==="login"?"Seu usuário ou e-mail":"voce@email.com";$("auth-submit").textContent=mode==="login"?"Entrar na sua reserva ↗":"Criar minha conta ↗";$("auth-error").textContent=""}
document.querySelectorAll(".tab").forEach(b=>b.onclick=()=>setMode(b.dataset.tab));
$("auth-form").onsubmit=async e=>{e.preventDefault();$("auth-error").textContent="";try{const path=authMode==="login"?"/auth/login":"/auth/register";const body=authMode==="login"?{identifier:$("email").value.trim(),password:$("password").value}:{username:$("username").value.trim().toLowerCase(),name:$("name").value,email:$("email").value.trim(),password:$("password").value};const d=await api(path,{method:"POST",body:JSON.stringify(body)});token=d.token;localStorage.setItem("sra_token",token);me=d.user;showApp();await loadMessages();await refreshActivity();}catch(err){$("auth-error").textContent=err.message}};
$("logout").onclick=()=>{token="";me=null;localStorage.removeItem("sra_token");localStorage.removeItem("sra_user");localStorage.removeItem("sra_current_conversation");showAuth()};
function escapeHtml(s){return s.replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
function addMessage(role,content){const box=document.createElement("div");box.className="message "+(role==="user"?"user":"");box.innerHTML=`<div class="msg-avatar">${role==="user"?"H":"✦"}</div><div class="bubble">${escapeHtml(content)}</div>`;$("messages").appendChild(box);$("messages").scrollTop=$("messages").scrollHeight}
async function loadMessages(){const d=await api("/messages");$("messages").innerHTML="";if(!d.messages.length){$("messages").innerHTML=document.querySelector(".welcome").outerHTML;$("welcome-name").textContent=me.name;document.querySelectorAll("[data-prompt]").forEach(b=>b.onclick=()=>sendMessage(b.dataset.prompt));return}d.messages.forEach(m=>addMessage(m.role,m.content))}
async function sendMessage(text){const value=(text??$("chat-input").value).trim();if(!value)return;$("chat-input").value="";$("messages").querySelector(".welcome")?.remove();addMessage("user",value);$("send").disabled=true;const pending=document.createElement("div");pending.className="message";pending.innerHTML='<div class="msg-avatar">✦</div><div class="bubble">Estou pensando…</div>';$("messages").appendChild(pending);$("messages").scrollTop=$("messages").scrollHeight;try{const d=await api("/chat",{method:"POST",body:JSON.stringify({message:value})});pending.remove();addMessage("assistant",d.reply)}catch(e){pending.remove();addMessage("assistant","Não consegui responder agora: "+e.message)}finally{$("send").disabled=false}}
$("chat-form").onsubmit=e=>{e.preventDefault();sendMessage()};$("chat-input").onkeydown=e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();sendMessage()}};$("new-chat").onclick=async()=>{if(confirm("Apagar o histórico desta conta?")){await api("/messages",{method:"DELETE"});await loadMessages();toast("Nova conversa iniciada.")}};
document.querySelectorAll("[data-prompt]").forEach(b=>b.onclick=()=>sendMessage(b.dataset.prompt));
function navigate(view){currentView=view;["chat","memories","activity","games"].forEach(v=>$(v+"-view").classList.toggle("hidden",v!==view));document.querySelectorAll(".nav").forEach(b=>b.classList.toggle("active",b.dataset.view===view));$("view-title").textContent={chat:"Um cantinho para conversar",memories:"Memórias especiais",activity:"Modo Atividade",games:"Jogos Soares"}[view];if(view==="memories")loadMemories();if(view==="activity")refreshActivity()}
document.querySelectorAll(".nav").forEach(b=>b.onclick=()=>navigate(b.dataset.view));
async function loadMemories(){const d=await api("/memories");$("memory-list").innerHTML="";if(!d.memories.length){$("memory-list").innerHTML='<p class="muted tiny">Ainda não há memórias salvas.</p>';return}d.memories.forEach(m=>{const el=document.createElement("div");el.className="memory-item";el.innerHTML=`<span>${escapeHtml(m.content)}</span><button title="Apagar">Excluir</button>`;el.querySelector("button").onclick=async()=>{await api("/memories/"+m.id,{method:"DELETE"});loadMemories();toast("Memória apagada.")};$("memory-list").appendChild(el)})}
$("memory-form").onsubmit=async e=>{e.preventDefault();const content=$("memory-input").value.trim();if(!content)return;try{await api("/memories",{method:"POST",body:JSON.stringify({content})});$("memory-input").value="";loadMemories();toast("Memória guardada 💜")}catch(err){toast(err.message)}};
async function refreshActivity(){try{const a=await api("/activity");isPlaying=a.is_playing;$("activity-title").textContent=isPlaying?`Soares está jogando${a.game?" "+a.game:""}`:"Soares está disponível";$("activity-sub").textContent=isPlaying?"A IA está aqui para conversar com você.": "Nenhuma atividade de jogo detectada."; $("activity-dot").classList.toggle("on",isPlaying);$("manual-activity").textContent=isPlaying?"Encerrar modo atividade":"Ativar modo estou jogando";$("status-text").textContent=isPlaying?"Soares está jogando":"Conectada"}catch(e){console.warn(e)}}
$("manual-activity").onclick=async()=>{try{await api("/activity",{method:"POST",body:JSON.stringify({is_playing:!isPlaying,game:"",source:"manual"})});await refreshActivity();toast("Status atualizado.")}catch(e){toast(e.message)}};
async function boot(){if(!token){showAuth();return}try{me=await api("/me");showApp();await loadMessages();await refreshActivity();setInterval(refreshActivity,15000)}catch(e){token="";localStorage.removeItem("sra_token");showAuth()}}
// Inicialização controlada no bloco Soares AI PRO ao final do arquivo.

// Mini games: rodam localmente no navegador, sem enviar dados ao servidor.
let gameTimer=null, gameScore=0, gameSeconds=20, ticBoard=[];
function stopGameTimers(){if(gameTimer)clearInterval(gameTimer);gameTimer=null}
function openGame(name){
 stopGameTimers();$("game-stage").classList.remove("hidden");$("game-content").innerHTML="";
 const titles={memory:"Jogo da memória",tic:"Jogo da velha",reaction:"Teste de reflexo"};$("game-title").textContent=titles[name]||"Minijogo";
 if(name==="memory")startMemory();if(name==="tic")startTic();if(name==="reaction")startReaction();
 $("game-stage").scrollIntoView({behavior:"smooth",block:"start"});
}
document.querySelectorAll("[data-game]").forEach(b=>b.onclick=()=>openGame(b.dataset.game));
$("game-back").onclick=()=>{stopGameTimers();$("game-stage").classList.add("hidden");$("game-content").innerHTML=""};
function startMemory(){
 const icons=["🌙","🌸","🦋","🍓","⭐","🐱","🎧","💜"];
 const deck=[...icons,...icons].sort(()=>Math.random()-.5);let first=null,lock=false,matches=0,moves=0;
 const root=$("game-content");root.innerHTML='<p class="game-info" id="memory-info">Encontre os 8 pares. Movimentos: 0</p><div class="game-board memory-board" id="memory-board"></div><button class="primary game-action" id="memory-reset">Jogar novamente</button>';
 const board=$("memory-board");
 deck.forEach(icon=>{const b=document.createElement("button");b.className="memory-tile";b.textContent="✦";b.setAttribute("aria-label","Carta fechada");b.onclick=()=>{if(lock||b.classList.contains("matched")||b===first)return;b.textContent=icon;b.classList.add("revealed");if(!first){first=b;return}moves++;const second=b;if(first.textContent===second.textContent){first.classList.add("matched");second.classList.add("matched");first.classList.remove("revealed");second.classList.remove("revealed");first.disabled=second.disabled=true;first=null;matches++;$("memory-info").textContent=matches===8?"Você venceu em "+moves+" movimentos! 🎉":"Encontre os 8 pares. Movimentos: "+moves;}else{lock=true;const prev=first;first=null;setTimeout(()=>{prev.textContent="✦";second.textContent="✦";prev.classList.remove("revealed");second.classList.remove("revealed");lock=false},750);$("memory-info").textContent="Encontre os 8 pares. Movimentos: "+moves}};board.appendChild(b)});
 $("memory-reset").onclick=startMemory;
}
function startTic(){
 ticBoard=Array(9).fill("");let ended=false;
 const root=$("game-content");root.innerHTML='<p class="game-info" id="tic-info">Sua vez! Você é X.</p><div class="game-board tic-board" id="tic-board"></div><button class="primary game-action" id="tic-reset">Jogar novamente</button>';
 const board=$("tic-board");
 function winner(b){for(const [a,c,d] of [[0,1,2],[3,4,5],[6,7,8],[0,3,6],[1,4,7],[2,5,8],[0,4,8],[2,4,6]])if(b[a]&&b[a]===b[c]&&b[a]===b[d])return b[a];return b.every(Boolean)?"draw":""}
 function render(){board.innerHTML="";ticBoard.forEach((v,i)=>{const b=document.createElement("button");b.className="tic-cell";b.textContent=v;b.disabled=!!v||ended;b.onclick=()=>{if(ended||ticBoard[i])return;ticBoard[i]="X";let w=winner(ticBoard);if(w){finish(w);render();return}const empty=ticBoard.map((v,j)=>v?null:j).filter(v=>v!==null);if(empty.length){const choice=empty[Math.floor(Math.random()*empty.length)];ticBoard[choice]="O"}w=winner(ticBoard);if(w)finish(w);render()};board.appendChild(b)})}
 function finish(w){ended=true;$("tic-info").textContent=w==="draw"?"Deu velha! 🤝":w==="X"?"Você venceu! 🎉":"A Soares AI venceu desta vez! 💜"}
 render();$("tic-reset").onclick=startTic;
}
function startReaction(){
 gameScore=0;gameSeconds=20;const root=$("game-content");
 root.innerHTML='<div class="game-info" id="reaction-info">Acerte o máximo de alvos em 20 segundos. Clique em começar!</div><div class="reaction-arena" id="reaction-arena"></div><button class="primary game-action" id="reaction-start">Começar</button>';
 const arena=$("reaction-arena");
 function spawn(){arena.innerHTML="";const t=document.createElement("button");t.className="reaction-target";t.textContent="✦";t.style.left=Math.max(0,Math.random()*(arena.clientWidth-58))+"px";t.style.top=Math.max(0,Math.random()*(arena.clientHeight-58))+"px";t.onclick=()=>{gameScore++;$("reaction-info").textContent="Tempo: "+gameSeconds+"s · Acertos: "+gameScore;spawn()};arena.appendChild(t)}
 $("reaction-start").onclick=()=>{gameScore=0;gameSeconds=20;$("reaction-start").disabled=true;$("reaction-info").textContent="Tempo: "+gameSeconds+"s · Acertos: 0";spawn();gameTimer=setInterval(()=>{gameSeconds--;$("reaction-info").textContent="Tempo: "+gameSeconds+"s · Acertos: "+gameScore;if(gameSeconds<=0){stopGameTimers();arena.innerHTML="";$("reaction-info").textContent="Fim de jogo! Você acertou "+gameScore+" alvos. 🎉";$("reaction-start").disabled=false;$("reaction-start").textContent="Jogar novamente"}},1000)};
}


// --- Recursos extras: Markdown seguro, voz, imagens e navegação ---
let pendingImageData = null;
let speakReplies = false;
function renderRichText(raw){
  let s=escapeHtml(String(raw??""));
  s=s.replace(/\*\*(.+?)\*\*/gs,"<strong>$1</strong>").replace(/__(.+?)__/gs,"<strong>$1</strong>");
  s=s.replace(/\*(?!\*)(.+?)\*(?!\*)/gs,"<em>$1</em>").replace(/`([^`]+)`/g,"<code>$1</code>");
  s=s.replace(/^### (.+)$/gm,"<h4>$1</h4>").replace(/^## (.+)$/gm,"<h3>$1</h3>").replace(/^# (.+)$/gm,"<h2>$1</h2>");
  s=s.replace(/\n/g,"<br>");
  return s;
}
addMessage = function(role,content){
  const box=document.createElement("div");box.className="message "+(role==="user"?"user":"");
  box.innerHTML='<div class="msg-avatar">'+(role==="user"?"H":"✦")+'</div><div class="bubble">'+renderRichText(content)+'</div>';
  $("messages").appendChild(box);$("messages").scrollTop=$("messages").scrollHeight;
  if(role==="assistant" && speakReplies) speakText(content);
};
const imagePick=$("image-pick"), imageFile=$("image-file"), imagePreview=$("image-preview");
imagePick.onclick=()=>imageFile.click();
imageFile.onchange=()=>{
 const f=imageFile.files?.[0]; if(!f)return;
 if(f.size>5*1024*1024){toast("A imagem deve ter até 5 MB.");imageFile.value="";return;}
 if(!/^image\/(png|jpeg|webp|gif)$/.test(f.type)){toast("Formato não suportado.");imageFile.value="";return;}
 const reader=new FileReader();reader.onload=()=>{pendingImageData=reader.result;imagePreview.innerHTML='<img alt="Prévia da imagem" src="'+pendingImageData+'"><button type="button" id="remove-image">Remover imagem ×</button>';imagePreview.classList.remove("hidden");$("remove-image").onclick=clearPendingImage;};reader.readAsDataURL(f);
};
function clearPendingImage(){pendingImageData=null;imageFile.value="";imagePreview.innerHTML="";imagePreview.classList.add("hidden")}
const originalSendMessage=sendMessage;
sendMessage=async function(text){
 const value=(text??$("chat-input").value).trim();
 if(!value&&!pendingImageData)return;
 const imageData=pendingImageData;clearPendingImage();$("chat-input").value="";
 $("messages").querySelector(".welcome")?.remove();
 addMessage("user",(value||"Analise esta imagem.")+(imageData?" [imagem anexada]":""));
 $("send").disabled=true;
 const pending=document.createElement("div");pending.className="message";pending.innerHTML='<div class="msg-avatar">✦</div><div class="bubble">Analisando…</div>';$("messages").appendChild(pending);
 try{const payload={message:value||"Descreva e analise a imagem enviada.",...(imageData?{image_data:imageData}:{})};
 const d=await api("/chat",{method:"POST",body:JSON.stringify(payload)});pending.remove();addMessage("assistant",d.reply);
 }catch(e){pending.remove();addMessage("assistant","Não consegui processar agora: "+e.message)}
 finally{$("send").disabled=false}
};
$("chat-form").onsubmit=e=>{e.preventDefault();sendMessage()};
const SpeechRecognition=window.SpeechRecognition||window.webkitSpeechRecognition;
$("voice-input").onclick=()=>{
 if(!SpeechRecognition){toast("Seu navegador não oferece reconhecimento de voz. Tente o Chrome ou Edge.");return}
 const rec=new SpeechRecognition();rec.lang="pt-BR";rec.interimResults=false;rec.maxAlternatives=1;
 $("voice-input").classList.add("recording");rec.onresult=e=>{$("chat-input").value=($("chat-input").value+" "+e.results[0][0].transcript).trim()};
 rec.onerror=()=>toast("Não foi possível captar sua voz.");rec.onend=()=>$("voice-input").classList.remove("recording");rec.start();toast("Pode falar…");
};
function speakText(text){if(!("speechSynthesis" in window)){toast("Leitura de voz não suportada neste navegador.");return}window.speechSynthesis.cancel();const u=new SpeechSynthesisUtterance(String(text).replace(/[*_#`]/g,""));u.lang="pt-BR";u.rate=1;window.speechSynthesis.speak(u)}
$("voice-output").onclick=()=>{speakReplies=!speakReplies;$("voice-output").classList.toggle("active",speakReplies);$("voice-output").textContent=speakReplies?"🔈":"🔊";toast(speakReplies?"Leitura das respostas ativada.":"Leitura das respostas desativada.")};
const oldNavigate=navigate;
navigate=function(view){if(view==="terms"){currentView=view;["chat","memories","activity","games","terms"].forEach(v=>$(v+"-view").classList.toggle("hidden",v!==view));document.querySelectorAll(".nav").forEach(b=>b.classList.toggle("active",b.dataset.view===view));$("view-title").textContent="Termos de uso";return}oldNavigate(view)};

// Jogos extras da aba Jogos Soares
const extraGames={
 quiz:{title:"Quiz Soares",questions:[["Qual é o planeta conhecido como planeta vermelho?",["Vênus","Marte","Júpiter"],1],["Quanto é 8 × 7?",["54","56","64"],1],["Qual destes é um navegador?",["Edge","Excel","Windows"],0],["Qual é o maior oceano da Terra?",["Atlântico","Índico","Pacífico"],2],["Qual linguagem estrutura páginas web?",["HTML","SQL","Python"],0]]},
 word:{title:"Palavra embaralhada",words:["ROXO","SOARES","JANELA","TECLADO","ESTRELA","GAMER"]}}
function startQuiz(){
 let idx=0,score=0;const q=extraGames.quiz.questions;const root=$("game-content");
 function render(){if(idx>=q.length){root.innerHTML='<p class="game-info">Quiz finalizado! Você acertou '+score+' de '+q.length+' perguntas. 🎉</p><button class="primary game-action" id="quiz-again">Jogar novamente</button>'; $("quiz-again").onclick=startQuiz;return}
 const item=q[idx];root.innerHTML='<p class="game-info">Pergunta '+(idx+1)+' de '+q.length+' · Pontos: '+score+'</p><h3 class="quiz-question">'+item[0]+'</h3><div class="quiz-options">'+item[1].map((a,i)=>'<button class="game-back quiz-option" data-answer="'+i+'">'+a+'</button>').join("")+'</div>';
 root.querySelectorAll("[data-answer]").forEach(btn=>btn.onclick=()=>{if(Number(btn.dataset.answer)===item[2])score++;idx++;render()})}
 render()
}
function startNumber(){
 const secret=Math.floor(Math.random()*100)+1;let tries=0;const root=$("game-content");
 root.innerHTML='<p class="game-info">Pensei em um número de 1 a 100. Você consegue descobrir?</p><form id="guess-form" class="guess-form"><input id="guess-value" type="number" min="1" max="100" required placeholder="Seu palpite"><button class="primary">Tentar</button></form><p class="game-info" id="guess-hint">Digite um palpite para começar.</p><button class="game-back" id="guess-again">Novo número</button>';
 $("guess-form").onsubmit=e=>{e.preventDefault();const n=Number($("guess-value").value);if(n<1||n>100)return;tries++;$("guess-hint").textContent=n===secret?"Acertou em "+tries+" tentativas! 🎉":n<secret?"Muito baixo! Tente um número maior.":"Muito alto! Tente um número menor.";if(n===secret)$("guess-hint").style.color="#69ffc7";$("guess-value").value=""};$("guess-again").onclick=startNumber;
}
function startWord(){
 let idx=0;const words=extraGames.word.words;const root=$("game-content");
 function render(){if(idx>=words.length){root.innerHTML='<p class="game-info">Você completou todas as palavras! 🏆</p><button class="primary game-action" id="word-again">Jogar novamente</button>';$("word-again").onclick=startWord;return}
 const answer=words[idx],scrambled=answer.split("").sort(()=>Math.random()-.5).join("");
 root.innerHTML='<p class="game-info">Palavra '+(idx+1)+' de '+words.length+'</p><h2 class="scrambled-word">'+scrambled+'</h2><form id="word-form" class="guess-form"><input id="word-value" required placeholder="Digite a palavra"><button class="primary">Conferir</button></form><p id="word-hint" class="game-info"></p>';
 $("word-form").onsubmit=e=>{e.preventDefault();if($("word-value").value.trim().toUpperCase()===answer){idx++;render()}else $("word-hint").textContent="Ainda não! Tente outra vez."}}
 render()
}
const previousOpenGame=openGame;
openGame=function(name){
 if(["quiz","number","word"].includes(name)){
 stopGameTimers();$("game-stage").classList.remove("hidden");$("game-content").innerHTML="";
 $("game-title").textContent=({quiz:"Quiz Soares",number:"Adivinhe o número",word:"Palavra embaralhada"})[name];
 if(name==="quiz")startQuiz();if(name==="number")startNumber();if(name==="word")startWord();
 $("game-stage").scrollIntoView({behavior:"smooth",block:"start"});return
 }previousOpenGame(name)
};
document.querySelectorAll("[data-game]").forEach(b=>b.onclick=()=>openGame(b.dataset.game));


// --- Perfil personalizável e chuva de caracteres cyber ---
let profileSymbol=localStorage.getItem("sra_profile_symbol")||"initial";
let profileColor=localStorage.getItem("sra_profile_color")||"violet";
const profileColorMap={violet:"linear-gradient(135deg,#a56bff,#5940a8)",blue:"linear-gradient(135deg,#65a7ff,#315caa)",mint:"linear-gradient(135deg,#5be0b1,#197e79)",pink:"linear-gradient(135deg,#ff83c8,#a34487)",orange:"linear-gradient(135deg,#ffb66b,#a54c29)"};
function avatarText(){return profileSymbol==="initial"?(me?.name||"H").trim().charAt(0).toUpperCase():profileSymbol}
function applyProfile(){
 const name=me?.name||"Visitante";$("profile-name").textContent=name;$("welcome-name").textContent=name;
 const avatar=$("profile-avatar");if(avatar){avatar.textContent=avatarText();avatar.style.background=profileColorMap[profileColor]||profileColorMap.violet}
 const preview=$("profile-preview-avatar");if(preview){preview.textContent=avatarText();preview.style.background=profileColorMap[profileColor]||profileColorMap.violet}
 const previewName=$("profile-preview-name");if(previewName)previewName.textContent=name;
 if($("profile-display-name"))$("profile-display-name").value=name;
 if($("profile-symbol"))$("profile-symbol").value=profileSymbol;
 document.querySelectorAll(".color-choice").forEach(b=>b.classList.toggle("selected",b.dataset.color===profileColor));
}
function initProfile(){
 $("profile-symbol").onchange=()=>{profileSymbol=$("profile-symbol").value;localStorage.setItem("sra_profile_symbol"+(me?.id?"_user_"+me.id:""),profileSymbol);applyProfile()};
 document.querySelectorAll(".color-choice").forEach(b=>b.onclick=()=>{profileColor=b.dataset.color;localStorage.setItem("sra_profile_color"+(me?.id?"_user_"+me.id:""),profileColor);applyProfile()});
 $("profile-form").onsubmit=async e=>{e.preventDefault();const name=$("profile-display-name").value.trim();if(name.length<2){toast("Digite um nome com pelo menos 2 caracteres.");return}
 try{me=await api("/me",{method:"PATCH",body:JSON.stringify({name})});applyProfile();toast("Perfil atualizado com sucesso 💜")}
 catch(err){toast("Não foi possível salvar: "+err.message)}
 };
}
function startHackerRain(){
 const root=$("hacker-rain");if(!root||root.dataset.ready)return;root.dataset.ready="1";
 const glyphs="01アイウエオカキクケコ{}[]<>/\\$#@";
 for(let i=0;i<34;i++){
  const col=document.createElement("span");col.className="rain-column";
  let str="";for(let n=0;n<12;n++)str+=glyphs[Math.floor(Math.random()*glyphs.length)]+" ";
  col.textContent=str;col.style.left=(i/34*100)+"%";
  col.style.setProperty("--fall-duration",(9+Math.random()*15)+"s");
  col.style.setProperty("--fall-delay",(-Math.random()*22)+"s");
  col.style.setProperty("--fall-opacity",(0.18+Math.random()*0.38).toFixed(2));
  root.appendChild(col);
 }
}
initProfile();startHackerRain();
const baseNavigate=navigate;
navigate=function(view){
 if(view==="terms"){baseNavigate(view);return}
 const views=["chat","memories","activity","games","profile"];
 views.forEach(v=>$(v+"-view")?.classList.toggle("hidden",v!==view));
 document.querySelectorAll(".nav").forEach(b=>b.classList.toggle("active",b.dataset.view===view));
 currentView=view;
 const titles={chat:"Um cantinho para conversar",memories:"Memórias especiais",activity:"Modo Atividade",games:"Jogos Soares",profile:"Personalizar perfil"};
 $("view-title").textContent=titles[view]||"Soares Reserva AI";
 if(view==="memories")loadMemories();if(view==="activity")refreshActivity();if(view==="profile")applyProfile();
};
document.querySelectorAll(".nav").forEach(b=>b.onclick=()=>navigate(b.dataset.view));


// --- Soares AI PRO: login verificado, Google e histórico persistente ---
let currentConversationId=null;
let pendingVerifyEmail="";
function matrixRain(targetId,count=34){
 const root=$(targetId);if(!root||root.dataset.ready==="1")return;
 root.dataset.ready="1";const chars="01アイウエオカキクケコサシスセソタチツテト<>[]{}/\\";
 for(let i=0;i<count;i++){
  const col=document.createElement("span");col.className="matrix-stream";
  let text="";for(let n=0;n<14+Math.floor(Math.random()*22);n++)text+=chars[Math.floor(Math.random()*chars.length)]+"\n";
  col.textContent=text;col.style.left=(i/count*100)+"%";col.style.setProperty("--speed",(8+Math.random()*13)+"s");
  col.style.setProperty("--delay",(-Math.random()*20)+"s");col.style.setProperty("--alpha",(0.22+Math.random()*.55).toFixed(2));
  root.appendChild(col);
 }
}
matrixRain("auth-matrix",42);
matrixRain("hacker-rain",34);

function finishLogin(d){
 token=d.token;localStorage.setItem("sra_token",token);me=d.user;localStorage.setItem("sra_user",JSON.stringify(me));currentConversationId=null;
 $("verify-panel")?.classList.add("hidden");showApp();
 loadConversations().then(loadMessages).catch(e=>toast(e.message));refreshActivity();
}
$("auth-form").onsubmit=async e=>{
 e.preventDefault();$("auth-error").textContent="";
 try{
  const email=$("email").value.trim().toLowerCase();
  if(authMode==="login"){
   const d=await api("/auth/login",{method:"POST",body:JSON.stringify({email,password:$("password").value})});
   finishLogin(d);
  }else{
   const d=await api("/auth/register",{method:"POST",body:JSON.stringify({name:$("name").value,email,password:$("password").value})});
   pendingVerifyEmail=d.email||email;$("verify-email-label").textContent=pendingVerifyEmail;$("verify-panel").classList.remove("hidden");
   $("auth-error").textContent=d.message||"Confira seu e-mail para confirmar a conta.";
  }
 }catch(err){
  $("auth-error").textContent=err.message;
  if(authMode==="register"&&/envio|confirmação|código/i.test(err.message)){
   pendingVerifyEmail=$("email").value.trim().toLowerCase();$("verify-email-label").textContent=pendingVerifyEmail;$("verify-panel").classList.remove("hidden");
  }
 }
};
$("verify-submit").onclick=async()=>{
 try{const d=await api("/auth/verify",{method:"POST",body:JSON.stringify({email:pendingVerifyEmail,code:$("verify-code").value.trim()})});finishLogin(d);toast("Conta confirmada. Acesso PRO liberado!")}
 catch(e){$("auth-error").textContent=e.message}
};
$("resend-code").onclick=async()=>{
 try{await api("/auth/resend",{method:"POST",body:JSON.stringify({email:pendingVerifyEmail})});toast("Novo código enviado.")}
 catch(e){$("auth-error").textContent=e.message}
};
async function handleGoogleCredential(response){
 try{const d=await api("/auth/google",{method:"POST",body:JSON.stringify({credential:response.credential})});finishLogin(d);toast("Login Google realizado. Acesso PRO ativo!")}
 catch(e){$("auth-error").textContent=e.message}
}
window.handleGoogleCredential=handleGoogleCredential;
(async()=>{
 try{
  const cfg=await api("/auth/config");
  if(!cfg.google_client_id)return;
  const script=document.createElement("script");script.src="https://accounts.google.com/gsi/client";script.async=true;script.defer=true;
  script.onload=()=>{
   if(!window.google?.accounts?.id)return;
   google.accounts.id.initialize({client_id:cfg.google_client_id,callback:handleGoogleCredential});
   google.accounts.id.renderButton($("google-signin"),{theme:"filled_black",size:"large",shape:"pill",text:"continue_with",width:300,logo_alignment:"left"});
  };
  document.head.appendChild(script);
 }catch(e){console.warn("Configuração Google indisponível",e)}
})();

async function loadConversations(){
 const d=await api("/conversations");let items=d.conversations||[];
 if(!items.length){const c=await api("/conversations",{method:"POST"});items=[c]}
 const saved=localStorage.getItem("sra_current_conversation");
 const preferred=currentConversationId||saved;
 if(preferred&&items.some(x=>String(x.id)===String(preferred)))currentConversationId=Number(preferred);
 else currentConversationId=items[0].id;
 localStorage.setItem("sra_current_conversation",String(currentConversationId));
 renderConversationList(items);
}
function renderConversationList(items){
 const root=$("conversation-list");if(!root)return;root.innerHTML="";
 items.forEach(item=>{
  const row=document.createElement("div");row.className="history-item"+(Number(item.id)===Number(currentConversationId)?" active":"");
  const open=document.createElement("button");open.type="button";open.className="history-open";open.textContent=item.title||"Nova conversa";open.title=item.title||"Nova conversa";
  open.onclick=async()=>{currentConversationId=Number(item.id);localStorage.setItem("sra_current_conversation",String(currentConversationId));renderConversationList(items);await loadMessages()};
  const del=document.createElement("button");del.type="button";del.className="history-delete";del.textContent="×";del.title="Excluir conversa";
  del.onclick=async()=>{if(!confirm("Excluir esta conversa permanentemente?"))return;try{await api("/conversations/"+item.id,{method:"DELETE"});if(Number(currentConversationId)===Number(item.id))currentConversationId=null;localStorage.removeItem("sra_current_conversation");await loadConversations();await loadMessages();toast("Conversa excluída.")}catch(e){toast(e.message)}};
  row.append(open,del);root.appendChild(row);
 });
}
loadMessages=async function(){
 if(!currentConversationId)await loadConversations();
 const d=await api("/messages?conversation_id="+encodeURIComponent(currentConversationId));
 $("messages").innerHTML="";
 if(!d.messages.length){
  const welcome=document.createElement("div");welcome.className="welcome";
  welcome.innerHTML='<div class="welcome-mark"><span>⟡</span><i></i></div><div class="eyebrow">SOARES AI / ONLINE</div><h1>Olá, <span id="welcome-name"></span> ✧</h1><p>Sua sessão está protegida. O que vamos criar hoje?</p><div class="suggestions"><button data-prompt="Quero conversar um pouquinho.">♡ Conversar</button><button data-prompt="Me ajuda a organizar meu dia?">✧ Organizar meu dia</button><button data-prompt="Me dá uma ideia divertida para hoje.">⌘ Uma ideia nova</button></div>';
  $("messages").appendChild(welcome);$("welcome-name").textContent=me?.name||"Visitante";
  welcome.querySelectorAll("[data-prompt]").forEach(b=>b.onclick=()=>sendMessage(b.dataset.prompt));return;
 }
 d.messages.forEach(m=>addMessage(m.role,m.content));
};
sendMessage=async function(text){
 const value=(text??$("chat-input").value).trim();if(!value&&!pendingImageData)return;
 if(!currentConversationId)await loadConversations();
 const imageData=pendingImageData;clearPendingImage();$("chat-input").value="";
 $("messages").querySelector(".welcome")?.remove();addMessage("user",(value||"Analise esta imagem.")+(imageData?" [imagem anexada]":""));
 $("send").disabled=true;const pending=document.createElement("div");pending.className="message";pending.innerHTML='<div class="msg-avatar">⟡</div><div class="bubble">Processando na rede Soares…</div>';$("messages").appendChild(pending);
 try{
  const payload={message:value||"Descreva e analise a imagem enviada.",conversation_id:currentConversationId,...(imageData?{image_data:imageData}:{})};
  const d=await api("/chat",{method:"POST",body:JSON.stringify(payload)});pending.remove();currentConversationId=Number(d.conversation_id||currentConversationId);localStorage.setItem("sra_current_conversation",String(currentConversationId));addMessage("assistant",d.reply);await loadConversations();
 }catch(e){pending.remove();addMessage("assistant","Não consegui processar agora: "+e.message)}
 finally{$("send").disabled=false}
};
$("new-chat").onclick=async()=>{
 try{const c=await api("/conversations",{method:"POST"});currentConversationId=Number(c.id);localStorage.setItem("sra_current_conversation",String(currentConversationId));await loadConversations();await loadMessages();$("chat-input").focus();toast("Nova conversa criada.")}
 catch(e){toast(e.message)}
};
async function bootPro(){
 if(!token){showAuth();return}
 try{me=JSON.parse(localStorage.getItem("sra_user")||"null")}catch{me=null}
 if(me)showApp();
 try{me=await api("/me");localStorage.setItem("sra_user",JSON.stringify(me));showApp();await loadConversations();await loadMessages();await refreshActivity();setInterval(refreshActivity,30000)}
 catch(e){
  if(/401|Sessão inválida|expirada|Faça login/i.test(e.message)){token="";me=null;localStorage.removeItem("sra_token");localStorage.removeItem("sra_user");showAuth()}
  else if(me){showApp();toast("Sem conexão no momento. Sua sessão continua salva.");}
  else{showAuth();toast("Não foi possível conectar. Tente novamente em instantes.");}
 }
}
bootPro();


// --- Soares AI: entrada direta, sessão rápida e perfil expandido ---
$("auth-form").onsubmit=async e=>{
 e.preventDefault();const submit=$("auth-submit");submit.disabled=true;submit.textContent=authMode==="login"?"Entrando…":"Criando sua conta…";$("auth-error").textContent="";
 try{
  const email=$("email").value.trim().toLowerCase();
   const body=authMode==="login"?{identifier:$("email").value.trim(),password:$("password").value}:{username:$("username").value.trim().toLowerCase(),name:$("name").value.trim(),email,password:$("password").value};
  const d=await api(authMode==="login"?"/auth/login":"/auth/register",{method:"POST",body:JSON.stringify(body)});
  finishLogin(d);if(authMode==="register")toast("Conta criada! Você já está dentro. ✦");
 }catch(err){$("auth-error").textContent=err.message}
 finally{submit.disabled=false;submit.textContent=authMode==="login"?"Entrar na sua conta ↗":"Criar minha conta ↗"}
};
let profilePrefsKey="sra_profile_preferences";
let profilePrefs=JSON.parse(localStorage.getItem(profilePrefsKey)||"{}");
let photoKey="sra_profile_photo";
let profilePhoto=localStorage.getItem(photoKey)||"";
const savePrefs=()=>localStorage.setItem(profilePrefsKey,JSON.stringify(profilePrefs));
const accentMap={violet:"#b28aff",mint:"#55e7b5",blue:"#67a9ff",rose:"#ff83bd",amber:"#ffc16b"};
const themeMap={midnight:["#0d0d14","#171722"],graphite:["#101317","#20262d"],violet:["#100c19","#21152e"],forest:["#081511","#10251e"]};
function applyExpandedProfile(){
 const name=me?.name||"Visitante", status=profilePrefs.status||"Disponível agora";
 $("profile-name").textContent=name;$("welcome-name").textContent=name;
 $("profile-preview-name").textContent=name;$("profile-preview-status").textContent=status;
 ["profile-avatar","profile-preview-avatar"].forEach(id=>{
  const el=$(id);if(!el)return;
  el.textContent=profilePhoto?"":(profileSymbol==="initial"?name.trim().charAt(0).toUpperCase():profileSymbol);
  el.style.background=profileColorMap[profileColor]||profileColorMap.violet;
  el.style.backgroundImage=profilePhoto?'url("'+profilePhoto+'")':"none";
  el.style.backgroundSize="cover";el.style.backgroundPosition="center";
 });
 if($("profile-display-name"))$("profile-display-name").value=name;
 if($("profile-status"))$("profile-status").value=status==="Disponível agora"?"":status;
 if($("profile-symbol"))$("profile-symbol").value=profileSymbol;
 for(const [id,key,def] of [["profile-theme","theme","midnight"],["profile-accent","accent","violet"],["profile-density","density","normal"],["profile-motion","motion","on"],["profile-rain","rain","on"]])if($(id))$(id).value=profilePrefs[key]||def;
 document.querySelectorAll(".color-choice").forEach(b=>b.classList.toggle("selected",b.dataset.color===profileColor));
 document.documentElement.style.setProperty("--user-accent",accentMap[profilePrefs.accent||"violet"]);
 const colors=themeMap[profilePrefs.theme||"midnight"];document.body.style.backgroundColor=colors[0];document.body.style.backgroundImage="radial-gradient(ellipse at 12% 8%, "+colors[1]+", transparent 40%)";
 document.body.dataset.density=profilePrefs.density||"normal";
 document.body.dataset.motion=profilePrefs.motion||"on";
 const rain=$("hacker-rain");if(rain){rain.style.display=profilePrefs.rain==="off"?"none":"";rain.style.opacity=profilePrefs.rain==="subtle"?".16":".46"}
}
function bindExpandedProfile(){
 $("profile-symbol").onchange=()=>{profileSymbol=$("profile-symbol").value;localStorage.setItem("sra_profile_symbol"+(me?.id?"_user_"+me.id:""),profileSymbol);applyExpandedProfile()};
 document.querySelectorAll(".color-choice").forEach(b=>b.onclick=()=>{profileColor=b.dataset.color;localStorage.setItem("sra_profile_color"+(me?.id?"_user_"+me.id:""),profileColor);applyExpandedProfile()});
 $("profile-photo").onchange=()=>{
  const file=$("profile-photo").files?.[0];if(!file)return;
  if(!file.type.startsWith("image/")){toast("Escolha um arquivo de imagem.");return}
  const reader=new FileReader();reader.onload=()=>{
   const img=new Image();img.onload=()=>{
    const canvas=document.createElement("canvas"),size=420,scale=Math.min(1,size/Math.max(img.width,img.height));canvas.width=Math.round(img.width*scale);canvas.height=Math.round(img.height*scale);
    canvas.getContext("2d").drawImage(img,0,0,canvas.width,canvas.height);
    profilePhoto=canvas.toDataURL("image/jpeg",.78);
    try{localStorage.setItem(photoKey,profilePhoto);applyExpandedProfile();updateAccountChrome();toast("Foto de perfil atualizada.")}
    catch(e){toast("A foto é grande demais para o armazenamento deste navegador.")}
   };img.src=reader.result;
  };reader.readAsDataURL(file);
 };
 $("remove-profile-photo").onclick=()=>{profilePhoto="";localStorage.removeItem(photoKey);$("profile-photo").value="";applyExpandedProfile();updateAccountChrome();toast("Foto removida.")};
 for(const id of ["profile-theme","profile-accent","profile-density","profile-motion","profile-rain"])$(id).onchange=()=>{profilePrefs[id.replace("profile-","")]= $(id).value;savePrefs();applyExpandedProfile()};
 $("profile-form").onsubmit=async e=>{
  e.preventDefault();const name=$("profile-display-name").value.trim();if(name.length<2)return toast("Digite um nome com pelo menos 2 caracteres.");
  try{me=await api("/me",{method:"PATCH",body:JSON.stringify({name})});profilePrefs.status=$("profile-status").value.trim()||"Disponível agora";savePrefs();applyExpandedProfile();toast("Perfil salvo.")}
  catch(err){toast("Não foi possível salvar: "+err.message)}
 };
 $("reset-profile-style").onclick=()=>{profilePrefs={};savePrefs();profileColor="violet";profileSymbol="initial";localStorage.setItem("sra_profile_color"+(me?.id?"_user_"+me.id:""),profileColor);localStorage.setItem("sra_profile_symbol"+(me?.id?"_user_"+me.id:""),profileSymbol);applyExpandedProfile();toast("Aparência restaurada.")};
}
bindExpandedProfile();applyExpandedProfile();
const oldProfileNavigate=navigate;
navigate=function(view){oldProfileNavigate(view);if(view==="profile")applyExpandedProfile()};
window.addEventListener("storage",e=>{if(e.key===photoKey){profilePhoto=e.newValue||"";applyExpandedProfile()}});

// Acorda o serviço gratuito do Render logo que a página abre, evitando que o primeiro login espere o cold start.
fetch(API_BASE+"/health",{cache:"no-store"}).catch(()=>{});


// --- Identidade de conta, avatares Soares e navegação ---
const avatarCatalog=[
 {id:"nebula",name:"Soares Nebula",symbol:"✦",a:"#7e5ce8",b:"#2c4d88"},
 {id:"pixel",name:"Soares Pixel",symbol:"▦",a:"#42c9aa",b:"#236a70"},
 {id:"aurora",name:"Soares Aurora",symbol:"☾",a:"#f18acb",b:"#624aa8"},
 {id:"phantom",name:"Soares Phantom",symbol:"◈",a:"#7883a8",b:"#222a42"},
 {id:"bloom",name:"Soares Bloom",symbol:"❀",a:"#f1a0b8",b:"#8855a2"},
 {id:"circuit",name:"Soares Circuit",symbol:"⌘",a:"#54d9dc",b:"#26518b"},
 {id:"comet",name:"Soares Comet",symbol:"☄",a:"#ffc16b",b:"#b45c53"},
 {id:"vortex",name:"Soares Vortex",symbol:"◎",a:"#b18aff",b:"#4b286e"}
];
let avatarStorageKey="sra_avatar";
let selectedSoaresAvatar=localStorage.getItem(avatarStorageKey)||"nebula";
function currentAvatar(){return avatarCatalog.find(a=>a.id===selectedSoaresAvatar)||avatarCatalog[0]}
function makeAvatarMarkup(extra=""){const a=currentAvatar();return '<span class="soares-avatar-art '+extra+'" style="--avatar-a:'+a.a+';--avatar-b:'+a.b+'">'+a.symbol+'</span>'}
function updateAccountChrome(){
 const pro=String(me?.email||"").toLowerCase().endsWith("@soaresdev.com");
 const badge=document.querySelector(".plan-badge");if(badge)badge.hidden=!pro;
 const role=$("profile-role");if(role)role.textContent=pro?"Conta PRO":"Conta padrão";
 document.querySelectorAll(".msg-avatar").forEach(el=>{if(el.dataset.role==="user"){el.innerHTML=makeAvatarMarkup("tiny-avatar")}});
 const profile=$("profile-avatar");if(profile&&!profilePhoto){const a=currentAvatar();profile.textContent=a.symbol;profile.style.background='linear-gradient(135deg,'+a.a+','+a.b+')'}
}
const originalAddMessage=addMessage;
addMessage=function(role,content){
 originalAddMessage(role,content);
 const el=$("messages").lastElementChild?.querySelector(".msg-avatar");if(el){el.dataset.role=role;if(role==="user"){el.innerHTML=makeAvatarMarkup("tiny-avatar")}else{el.textContent="✦"}}
};
function renderAvatarPicker(){
 const host=$("soares-avatar-picker");if(!host)return;host.innerHTML="";
 avatarCatalog.forEach(a=>{
  const btn=document.createElement("button");btn.type="button";btn.className="avatar-preset"+(a.id===selectedSoaresAvatar?" selected":"");
  btn.innerHTML='<span class="soares-avatar-art" style="--avatar-a:'+a.a+';--avatar-b:'+a.b+'">'+a.symbol+'</span><b>'+a.name+'</b>';
  btn.onclick=()=>{selectedSoaresAvatar=a.id;localStorage.setItem(avatarStorageKey,a.id);renderAvatarPicker();applyExpandedProfile();updateAccountChrome();decorateGameCards();decorateGameStage();toast(a.name+" selecionado.")};
  host.appendChild(btn);
 });
}
function openProfileSettings(){navigate("profile");renderAvatarPicker();document.querySelector(".profile-page")?.scrollIntoView({behavior:"smooth",block:"start"})}
const profileFooter=$(".profile");
if(profileFooter){profileFooter.setAttribute("role","button");profileFooter.setAttribute("tabindex","0");profileFooter.setAttribute("aria-label","Abrir configurações do perfil");profileFooter.addEventListener("click",e=>{if(e.target.closest("#logout"))return;openProfileSettings()});profileFooter.addEventListener("keydown",e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();openProfileSettings()}})}
const logoutButton=$("logout");if(logoutButton)logoutButton.addEventListener("click",e=>e.stopPropagation());
updateAccountChrome();renderAvatarPicker();
const baseShowApp=showApp;
showApp=function(){baseShowApp();switchProfileStorage();updateAccountChrome();};
function switchProfileStorage(){
 if(!me?.id)return;
 const suffix="_user_"+me.id;
 profilePrefsKey="sra_profile_preferences"+suffix;photoKey="sra_profile_photo"+suffix;avatarStorageKey="sra_avatar"+suffix;
 profilePrefs=JSON.parse(localStorage.getItem(profilePrefsKey)||"{}");
 profilePhoto=localStorage.getItem(photoKey)||"";
 selectedSoaresAvatar=localStorage.getItem(avatarStorageKey)||"nebula";
 profileColor=localStorage.getItem("sra_profile_color"+suffix)||"violet";
 profileSymbol=localStorage.getItem("sra_profile_symbol"+suffix)||"initial";
 applyExpandedProfile();renderAvatarPicker();updateAccountChrome();
}
const baseApplyExpandedProfile=applyExpandedProfile;
applyExpandedProfile=function(){baseApplyExpandedProfile();if(!profilePhoto){const a=currentAvatar();["profile-avatar","profile-preview-avatar"].forEach(id=>{const el=$(id);if(el){el.textContent=a.symbol;el.style.background='linear-gradient(135deg,'+a.a+','+a.b+')';el.style.backgroundImage="none"}})}};
const baseProfileColorSet=localStorage.setItem.bind(localStorage);
const previousNavigateFinal=navigate;
navigate=function(view){
 const views=["chat","memories","activity","games","profile","terms"];
 views.forEach(v=>$(v+"-view")?.classList.toggle("hidden",v!==view));
 document.querySelectorAll(".nav").forEach(b=>b.classList.toggle("active",b.dataset.view===view));
 currentView=view;
 const titles={chat:"Conversas",memories:"Minhas memórias",activity:"Modo atividade",games:"Jogos Soares",profile:"Configurações do perfil",terms:"Termos de uso"};
 $("view-title").textContent=titles[view]||"Soares AI";
 if(view==="memories")loadMemories();if(view==="activity")refreshActivity();if(view==="profile"){applyExpandedProfile();renderAvatarPicker()}
 if(view==="chat"&&currentConversationId)loadMessages().catch(e=>toast(e.message));
};

function decorateGameCards(){
 document.querySelectorAll(".game-card").forEach(card=>{
  let stamp=card.querySelector(".game-avatar-stamp");
  if(!stamp){stamp=document.createElement("span");stamp.className="game-avatar-stamp";card.appendChild(stamp)}
  stamp.innerHTML=makeAvatarMarkup("tiny-avatar")+'<small>Seu personagem</small>';
 });
}
function decorateGameStage(){
 const head=document.querySelector(".game-stage-head");if(!head)return;
 let strip=head.querySelector(".game-players");if(!strip){strip=document.createElement("div");strip.className="game-players";head.appendChild(strip)}
 const user=currentAvatar();
 strip.innerHTML='<div class="game-player"><span class="soares-avatar-art" style="--avatar-a:'+user.a+';--avatar-b:'+user.b+'">'+user.symbol+'</span><small>Você</small></div><span class="game-vs">VS</span><div class="game-player"><span class="soares-avatar-art" style="--avatar-a:#67d8bd;--avatar-b:#285d70">✦</span><small>Soares AI</small></div>';
}
document.querySelectorAll("[data-game]").forEach(card=>card.addEventListener("click",()=>setTimeout(()=>{decorateGameCards();decorateGameStage()},0)));
decorateGameCards();
