"use strict";
const $ = (id) => document.getElementById(id);
const form = $("create-form");
let authenticated = false, submitting = false, draftTimer, lastJobs = "", lastStatus = "", pollRunning = false;
let uncertainRequest = null;
const draftKey = "music-creator-draft-v1";
const themes=new Set(["blue","violet","sea","apricot","rose"]), themeKey="music-creator-theme-v1";
function setTheme(value){const theme=themes.has(value)?value:"blue";document.documentElement.dataset.theme=theme;$("theme-select").value=theme;}
try{setTheme(localStorage.getItem(themeKey));}catch{setTheme("blue");}
$("theme-select").addEventListener("change",()=>{setTheme($("theme-select").value);try{localStorage.setItem(themeKey,$("theme-select").value);}catch{}document.dispatchEvent(new Event("music-theme-change"));});
let audioContext, playbackIntent=0, currentPlaying=null, modelProcessing=false, modelConnected=false, modelBlocked=false, currentJobs=[];
const audioGraphs=new WeakMap(), playerDisposals=new WeakMap(), reducedMotion=matchMedia("(prefers-reduced-motion: reduce)");
document.querySelectorAll("[data-bars]").forEach(clip=>{
  for(let i=0;i<Number(clip.dataset.bars);i++){const bar=document.createElement("i");bar.style.setProperty("--bar",`${4+Math.abs(Math.sin(i*1.7))*14}px`);bar.style.setProperty("--delay",`${i*-.17}s`);clip.append(bar);}
});
function studioState(){
  const active=currentJobs.find(job=>["submitting","running","generating","downloading"].includes(job.status));
  const blocked=modelBlocked||currentJobs.some(job=>["unknown","waiting","paused"].includes(job.status));
  const playing=!!currentPlaying&&!currentPlaying.paused;
  $("studio-stage").classList.toggle("is-playing",playing);$("studio-stage").classList.toggle("is-generating",!!active||modelProcessing);
  $("stage-state").textContent=playing?"正在试听":modelProcessing?"正在写词":active?"正在生成":blocked?"需要核实":modelConnected?"准备创作":"等待连接";
  $("stage-caption").textContent=playing?currentPlaying.dataset.title:modelProcessing?"写好歌词，再开始谱曲":active?active.title||"音乐正在生成":blocked?"先核实或恢复上次任务":modelConnected?"把下一段灵感留在这里":"等待电脑上的音乐模型";
}
function stopPlayers(){playbackIntent++;document.querySelectorAll("audio").forEach(audio=>audio.pause());currentPlaying=null;studioState();}
function disposeCard(card){card.querySelector("audio")?.pause();playerDisposals.get(card)?.();}
function clock(seconds){if(!Number.isFinite(seconds))return "--:--";const value=Math.max(0,Math.floor(seconds));return `${Math.floor(value/60)}:${String(value%60).padStart(2,"0")}`;}
async function audioGraph(audio){
  const Context=window.AudioContext||window.webkitAudioContext;
  if(!Context)return null;
  try{
    audioContext ||= new Context();
    await audioContext.resume();
    if(audioContext.state!=="running")return null;
    if(!audioGraphs.has(audio)){
      const analyser=audioContext.createAnalyser();analyser.fftSize=256;
      const source=audioContext.createMediaElementSource(audio);
      source.connect(audioContext.destination);source.connect(analyser);
      audioGraphs.set(audio,{source,analyser,samples:new Uint8Array(analyser.fftSize)});
    }
    return audioGraphs.get(audio);
  }catch{return null;}
}
function buildPlayer(card,audio,title){
  const player=el("div","deck-player"), canvas=el("canvas","waveform");canvas.width=640;canvas.height=90;canvas.setAttribute("aria-hidden","true");
  player.setAttribute("aria-live","off");
  const caption=el("div","wave-caption","播放后显示实时波形"),controls=el("div","player-controls"),button=el("button","play-toggle");button.type="button";
  const icon=el("span","play-symbol"),label=el("span","","试听");icon.setAttribute("aria-hidden","true");button.append(icon,label);
  const seek=el("input","seek");seek.type="range";seek.min="0";seek.max="1000";seek.step="1";seek.value="0";seek.disabled=true;seek.setAttribute("aria-label",`播放进度 ${title}`);
  const time=el("span","time-display","0:00 / --:--"),error=el("p","error player-error");error.setAttribute("role","alert");
  controls.append(button,seek,time);player.append(canvas,caption,controls,error);card.append(audio,player);audio.dataset.title=title;
  let frame=0;const events=new AbortController();
  playerDisposals.set(card,()=>{cancelAnimationFrame(frame);events.abort();const graph=audioGraphs.get(audio);graph?.source.disconnect();graph?.analyser.disconnect();audioGraphs.delete(audio);});
  function paint(){
    cancelAnimationFrame(frame);frame=0;
    const context=canvas.getContext("2d");if(!context)return;
    const graph=audioGraphs.get(audio),active=!audio.paused&&!audio.ended&&graph&&!reducedMotion.matches;
    const themeColors=getComputedStyle(document.documentElement),wave=themeColors.getPropertyValue("--mint").trim(),idle=themeColors.getPropertyValue("--wave-idle").trim();
    context.clearRect(0,0,640,90);
    if(active){
      graph.analyser.getByteTimeDomainData(graph.samples);context.strokeStyle=wave;context.lineWidth=2;context.beginPath();
      const peak=Math.max(4,...graph.samples.map(sample=>Math.abs(sample-128)));
      graph.samples.forEach((sample,i)=>{const x=i/(graph.samples.length-1)*640,y=45+(sample-128)/peak*35;i?context.lineTo(x,y):context.moveTo(x,y);});context.stroke();
    }else{
      const progress=Number.isFinite(audio.duration)&&audio.duration>0?audio.currentTime/audio.duration:0;
      for(let i=0;i<64;i++){const height=8+Math.abs(Math.sin(i*.61)*Math.cos(i*.23))*42;context.fillStyle=i/64<progress?wave:idle;context.fillRect(i*10+2,(90-height)/2,3,height);}
    }
    if(!audio.paused&&!document.hidden&&!reducedMotion.matches)frame=requestAnimationFrame(paint);
  }
  function update(){
    const available=Number.isFinite(audio.duration)&&audio.duration>0;
    seek.disabled=!available;seek.value=available?String(Math.round(audio.currentTime/audio.duration*1000)):"0";
    seek.setAttribute("aria-valuetext",`${clock(audio.currentTime)} / ${clock(audio.duration)}`);time.textContent=`${clock(audio.currentTime)} / ${clock(audio.duration)}`;
    button.setAttribute("aria-label",`${audio.paused?"播放":"暂停"} ${title}`);label.textContent=audio.paused?"试听":"暂停";
    caption.textContent=audio.paused?"播放后显示实时波形":reducedMotion.matches?"正在播放 · 动画已减少":audioGraphs.has(audio)?"正在显示实时声音波形":"正在播放 · 时间进度实时更新";
  }
  button.addEventListener("click",async()=>{
    if(!audio.paused){playbackIntent++;audio.pause();return;}
    const intent=++playbackIntent;document.querySelectorAll("audio").forEach(other=>{if(other!==audio)other.pause();});error.textContent="";button.disabled=true;
    try{
      await audioGraph(audio);
      if(intent!==playbackIntent||!card.isConnected||!authenticated){if(!card.isConnected)disposeCard(card);return;}
      await audio.play();
      if(intent!==playbackIntent||!card.isConnected||!authenticated){audio.pause();if(!card.isConnected)disposeCard(card);}
    }
    catch{error.textContent="暂时无法播放。请重新连接工作台，或下载 WAV 在本机试听。";}
    finally{button.disabled=false;}
  });
  seek.addEventListener("input",()=>{if(Number.isFinite(audio.duration)&&audio.duration>0)audio.currentTime=Number(seek.value)/1000*audio.duration;update();});
  audio.addEventListener("loadedmetadata",()=>{update();paint();});audio.addEventListener("timeupdate",()=>{update();if(audio.paused||reducedMotion.matches)paint();});
  audio.addEventListener("play",()=>{currentPlaying=audio;card.classList.add("playing");caption.textContent=audioGraphs.has(audio)?"正在显示实时声音波形":"正在播放 · 时间进度实时更新";update();studioState();cancelAnimationFrame(frame);paint();});
  for(const event of ["pause","ended"])audio.addEventListener(event,()=>{card.classList.remove("playing");if(currentPlaying===audio)currentPlaying=null;caption.textContent="播放后显示实时波形";cancelAnimationFrame(frame);update();paint();studioState();});
  audio.addEventListener("error",()=>{error.textContent="音频读取失败。请检查电脑工作台，再尝试试听或下载。";});
  document.addEventListener("visibilitychange",()=>{cancelAnimationFrame(frame);if(!document.hidden&&card.isConnected)paint();},{signal:events.signal});
  reducedMotion.addEventListener("change",()=>{cancelAnimationFrame(frame);if(card.isConnected){update();paint();}},{signal:events.signal});update();paint();
  document.addEventListener("music-theme-change",()=>{if(card.isConnected)paint();},{signal:events.signal});
}
function confirmAction(message){
  const dialog=$("action-confirm");
  if(dialog.open)return Promise.resolve(false);
  $("confirm-message").textContent=message;
  return new Promise(resolve=>{
    const finish=()=>{dialog.removeEventListener("close",finish);resolve(dialog.returnValue==="confirm");};
    dialog.addEventListener("close",finish);
    dialog.returnValue="cancel";
    dialog.showModal();
  });
}
function selectSection(id){document.querySelectorAll('.workspace-nav a').forEach(link=>{const selected=link.hash===`#${id}`;link.classList.toggle('selected',selected);if(selected)link.setAttribute('aria-current','location');else link.removeAttribute('aria-current');});}
document.querySelectorAll('.workspace-nav a').forEach(link=>link.addEventListener('click',()=>selectSection(link.hash.slice(1))));
const presets = {
  pet: {title:"和小狗一起的周末",description:"小狗在草地上奔跑的短视频，温暖、轻快，简单鼓点与木吉他，音乐不要盖过旁白，结尾自然收束。",style:"acoustic pop",mood:"upbeat"},
  night: {title:"晚风经过的地方",description:"夜晚一个人沿着街道散步，路灯和晚风，安静、有一点期待，轻柔钢琴和松弛节奏。",style:"lo-fi",mood:"calm"},
  story: {title:"故事还在继续",description:"故事结尾，人物走向新的生活，从平静走向温暖的希望，钢琴与柔和弦乐，收尾留白。",style:"cinematic",mood:"emotional"}
};
async function api(path, options={}) {
  const headers = {...options.headers};
  if (options.body) headers["Content-Type"] = "application/json";
  const response = await fetch(path, {...options, headers, credentials:"same-origin"});
  const data = await response.json().catch(() => ({error:"工作台响应异常，请检查电脑上的启动窗口。"}));
  if (!response.ok) {
    if (response.status === 401 && path !== "/api/session") showPairing();
    const error = new Error(data.error || data.message || "操作未完成，请稍后再试。");
    error.httpStatus = response.status;
    throw error;
  }
  return data;
}
function mode(){return form.elements.mode.value;}
function updateMode(){
  const song=mode()==="song", auto=form.elements.lyric_mode.value==="auto";
  $("song-fields").hidden=!song; $("lyrics-field").hidden=false; $("auto-notice").hidden=!auto;
  $("voice-preferences").hidden=!song;
  const instruments=[...form.querySelectorAll('[name="instruments"]')], count=instruments.filter(input=>input.checked).length;
  instruments.forEach(input=>{input.disabled=count>=3&&!input.checked;});
  $("instrument-count").textContent=`${count} / 3`;
  $("lyrics").required=song;
  $("description-label").textContent=song?"你想唱一个怎样的故事？":"这段音乐用在什么地方？";
  $("generate-label").textContent=song?"生成这首歌":"生成一段 BGM";
  $("duration-hint").textContent=song?"第一次写歌可以先做 1 分钟，歌词太长容易唱不完。":"短视频配乐先试 30 秒，每次生成一个版本。";
}
function fields(){const values=new FormData(form),data=Object.fromEntries(values);data.duration=Number(data.duration);data.instruments=values.getAll("instruments").sort();return data;}
function saveDraft(){
  try{localStorage.setItem(draftKey,JSON.stringify(fields()));$("draft-status").textContent="草稿已保存在此浏览器";}
  catch{$("draft-status").textContent="浏览器无法保存草稿，请自行留存歌词";}
}
function fill(values){
  for(const [key,value] of Object.entries(values)){
    if(key==="instruments"&&Array.isArray(value)){const inputs=[...form.querySelectorAll('[name="instruments"]')], selected=inputs.filter(input=>value.includes(input.value)).slice(0,3);inputs.forEach(input=>{input.checked=selected.includes(input);});continue;}
    if(form.elements[key] && typeof value!=="object") form.elements[key].value=String(value);
  }
  updateMode();
}
try{const draft=JSON.parse(localStorage.getItem(draftKey)||"null");if(draft&&typeof draft==="object")fill(draft);}catch{}
form.addEventListener("input",()=>{updateMode();clearTimeout(draftTimer);draftTimer=setTimeout(saveDraft,350);});
form.addEventListener("change",()=>{updateMode();saveDraft();});
document.querySelectorAll("[data-preset]").forEach(button=>button.addEventListener("click",()=>{
  fill(presets[button.dataset.preset]);saveDraft();$("description").focus();
}));
function showPairing(){stopPlayers();authenticated=false;lastStatus="";$("workspace").hidden=true;$("pairing").hidden=false;$("logout").hidden=true;$("connection").classList.remove("online","working");$("connection").lastElementChild.textContent="等待配对";}
async function showWorkspace(){authenticated=true;$("pairing").hidden=true;$("workspace").hidden=false;$("logout").hidden=false;updateMode();await refresh();}
$("pair-form").addEventListener("submit",async event=>{
  event.preventDefault();const button=event.currentTarget.querySelector("button");button.disabled=true;$("pair-error").textContent="";
  try{await api("/api/session",{method:"POST",body:JSON.stringify({code:$("pair-code").value.trim()})});$("pair-code").value="";await showWorkspace();}
  catch(error){$("pair-error").textContent=error.message;}
  finally{button.disabled=false;}
});
$("logout").addEventListener("click",async()=>{try{await api("/api/session",{method:"DELETE"});stopPlayers();[...$("jobs").children].forEach(disposeCard);$("jobs").replaceChildren();lastJobs="";currentJobs=[];showPairing();}catch(error){$("library-error").textContent=error.message;}});
function requestId(){if(globalThis.crypto?.randomUUID)return crypto.randomUUID();const bytes=crypto.getRandomValues(new Uint8Array(16));return Array.from(bytes,b=>b.toString(16).padStart(2,"0")).join("");}
$("draft-lyrics").addEventListener("click",async()=>{
  if(!$("description").reportValidity())return;
  if($("lyrics").value.trim()&&!await confirmAction("新的歌词草稿会替换当前歌词。请先保存想保留的内容，再确认继续。"))return;
  const button=$("draft-lyrics");button.disabled=true;$("generate").disabled=true;$("lyrics-status").textContent="正在根据主题写歌词，请稍等。";
  const initialLyrics=$("lyrics").value;
  try{
    const data=await api("/api/lyrics",{method:"POST",body:JSON.stringify(fields())});
    if($("lyrics").value!==initialLyrics){$("lyrics-status").textContent="你在等待时修改了歌词，已保留你的编辑。AI 草稿显示在下方。";const details=el("details");details.open=true;details.append(el("summary","","AI 歌词草稿"),el("pre","",data.lyrics));$("lyrics-status").append(details);}
    else{$("lyrics").value=data.lyrics;saveDraft();$("lyrics-status").textContent="歌词草稿已写好。轻量模型可能偏题或写得过长，请检查并改词，再生成歌曲。";}
  }catch(error){$("lyrics-status").textContent=error.message;}
  finally{button.disabled=false;$("generate").disabled=false;}
});
form.addEventListener("submit",async event=>{
  event.preventDefault();if(submitting)return;
  const data=fields();data.lyric_mode="manual";const fingerprint=JSON.stringify(data);
  if(!uncertainRequest||uncertainRequest.fingerprint!==fingerprint)uncertainRequest={fingerprint,id:requestId()};
  data.request_id=uncertainRequest.id;submitting=true;$("generate").disabled=true;$("create-error").textContent="";saveDraft();
  try{await api("/api/jobs",{method:"POST",body:JSON.stringify(data)});uncertainRequest=null;await refresh();selectSection('library-title');$("library-title").scrollIntoView({behavior:matchMedia("(prefers-reduced-motion: reduce)").matches?"instant":"smooth",block:"start"});}
  catch(error){$("create-error").textContent=error.message;if(!error.httpStatus)$("create-error").textContent+=" 请先刷新作品列表；保持输入不变再提交会复用本次请求。";}
  finally{submitting=false;$("generate").disabled=false;}
});
function el(tag,cls,text){const element=document.createElement(tag);if(cls)element.className=cls;if(text!==undefined)element.textContent=text;return element;}
const statusText={queued:"已加入队列，轮到这段音乐时会开始生成。",submitting:"正在把你的想法交给音乐模型。",running:"音乐正在生成，时间取决于时长和电脑状态。",generating:"音乐正在生成，时间取决于时长和电脑状态。",downloading:"生成完成，正在保存音频。",succeeded:"已保存，可以试听了。",completed:"已保存，可以试听了。",failed:"这次未能生成，请查看下方原因。",unknown:"上次提交结果不确定，请检查模型服务，避免重复生成。",interrupted:"任务已中断，请检查电脑上的模型服务。",paused:"等待模型恢复连接。"};
statusText.waiting="连接暂时中断，正在保留任务并等待恢复。";
function safeAudioUrl(value){return typeof value==="string"&&/^\/audio\/[a-zA-Z0-9_-]+\.wav(?:\?[^#]*)?$/.test(value)?value:null;}
const voiceNames={female:"女声",male:"男声"},toneNames={clear:"清亮",warm:"温暖",husky:"沙哑",breathy:"轻柔气声",powerful:"有力量"};
const instrumentNames={piano:"钢琴",acoustic_guitar:"木吉他",electric_guitar:"电吉他",strings:"弦乐",bass:"贝斯",drums:"鼓组",synth:"合成器",guzheng:"古筝",flute:"长笛"};
function preferenceSummary(job){const parts=[];if(job.mode==="song"){if(voiceNames[job.voice_gender])parts.push(voiceNames[job.voice_gender]);if(toneNames[job.voice_tone])parts.push(toneNames[job.voice_tone]);}if(Array.isArray(job.instruments))parts.push(...job.instruments.map(value=>instrumentNames[value]).filter(Boolean));return parts.join(" · ");}
function renderJobs(jobs){
  currentJobs=jobs;studioState();
  const signature=JSON.stringify(jobs);if(signature===lastJobs)return;lastJobs=signature;
  $("job-count").textContent=String(jobs.length);$("nav-count").textContent=String(jobs.length);$("empty-state").hidden=jobs.length>0;
  const container=$("jobs");const existing=new Map([...container.children].map(node=>[node.dataset.jobId,node]));
  for(const job of jobs){
    const jobSignature=JSON.stringify(job);let card=existing.get(job.id);existing.delete(job.id);
    if(card&&card.dataset.signature===jobSignature)continue;
    const fresh=el("article","track panel");fresh.dataset.jobId=job.id;fresh.dataset.signature=jobSignature;
    const heading=el("div","track-heading");heading.append(el("span","track-icon",job.mode==="song"?"♪":"♫"));
    const titles=el("div");titles.append(el("h3","",job.title||(job.mode==="song"?"我的歌曲":"我的配乐")));
    let date="";if(job.created_at){const parsed=new Date(typeof job.created_at==="number"?job.created_at*1000:job.created_at);if(!isNaN(parsed))date=parsed.toLocaleString("zh-CN",{month:"short",day:"numeric",hour:"2-digit",minute:"2-digit"});}
    titles.append(el("div","track-meta",`${job.mode==="song"?"中文歌曲":"纯音乐"} · 目标 ${job.duration} 秒${date?" · "+date:""}`));heading.append(titles);fresh.append(heading);
    fresh.append(el("p","track-description",job.description||""));
    const preferences=preferenceSummary(job);if(preferences)fresh.append(el("p","track-preferences","创作偏好："+preferences));
    const audioUrl=safeAudioUrl(job.audio_url);
    if(audioUrl){const audio=el("audio");audio.hidden=true;audio.preload="metadata";audio.src=audioUrl;buildPlayer(fresh,audio,job.title||"作品");}
    else{fresh.append(el("p","status "+job.status,statusText[job.status]||"正在等待任务更新。"));if(["queued","running","generating","submitting","downloading"].includes(job.status))fresh.append(el("div","progress-line"));}
    if(job.error)fresh.append(el("p","error",job.error));
    const actions=el("div","track-actions");
    if(["unknown","running","waiting","paused"].includes(job.status)){
      const resolve=el("button","",job.status==="unknown"?"核实后解除等待":"结束本地等待");resolve.type="button";
      resolve.addEventListener("click",async()=>{
        if(!await confirmAction("请先在电脑上确认音乐模型已完成或停止这次任务。此操作只结束工作台的等待，不会取消模型运算，也不会重新提交或找回音频。确认已核实？"))return;
        resolve.disabled=true;
        const action=job.status==="unknown"?"resolve-unknown":"resolve-waiting";
        try{await api(`/api/jobs/${encodeURIComponent(job.id)}/${action}`,{method:"POST",body:JSON.stringify({confirmed:true})});await refresh();}
        catch(error){$("library-error").textContent=error.message;resolve.disabled=false;}
      });actions.append(resolve);
    }
    if(audioUrl){const link=el("a","","下载 WAV");link.href=safeAudioUrl(job.download_url)||audioUrl+"?download=1";link.download="";actions.append(link);}
    if(job.status==="paused") {const resume=el("button","","恢复查询");resume.type="button";resume.addEventListener("click",async()=>{resume.disabled=true;try{await api(`/api/jobs/${encodeURIComponent(job.id)}/resume`,{method:"POST",body:"{}"});await refresh();}catch(error){$("library-error").textContent=error.message;}finally{resume.disabled=false;}});actions.append(resume);}
    const reuse=el("button","","沿用这个想法");reuse.type="button";reuse.addEventListener("click",()=>{fill({mode:job.mode,title:job.title||"",description:job.description||"",style:job.style||"acoustic pop",mood:job.mood||"warm",duration:job.duration||30,lyrics:job.lyrics||"",lyric_mode:job.lyric_mode||"manual",voice_gender:job.voice_gender||"auto",voice_tone:job.voice_tone||"auto",instruments:job.instruments||[]});saveDraft();$("composer-title").scrollIntoView({block:"start",behavior:"smooth"});});actions.append(reuse);fresh.append(actions);
    if(job.mode==="song"&&job.lyrics){const details=el("details");details.append(el("summary","","查看歌词"),el("pre","",job.lyrics));fresh.append(details);}
    if(card){disposeCard(card);card.replaceWith(fresh);}else container.append(fresh);
  }
  for(const node of existing.values()){disposeCard(node);node.remove();}
  for(const job of jobs){const node=[...container.children].find(item=>item.dataset.jobId===job.id);if(node)container.append(node);}
}
async function refresh(){
  if(!authenticated||pollRunning)return;pollRunning=true;
  try{
    const results=await Promise.allSettled([api("/api/status"),api("/api/jobs")]);
    if(!authenticated)return;
    if(results[0].status==="fulfilled"){
      const signature=JSON.stringify(results[0].value);
      modelProcessing=!!results[0].value.processing_lyrics;modelConnected=!!results[0].value.connected;modelBlocked=!!results[0].value.model_uncertain;studioState();
      if(signature!==lastStatus){lastStatus=signature;
      const status=results[0].value, processing=!!status.processing_lyrics;$("connection").classList.toggle("online",!!status.connected);$("connection").classList.toggle("working",processing);$("connection").lastElementChild.textContent=processing?"正在写歌词":status.connected?"音乐模型已连接":"模型尚未连接";
      const notice=$("engine-notice");notice.hidden=processing||(!!status.connected&&!status.model_uncertain&&status.lyrics_ready!==false);
      notice.textContent=status.message||"请在电脑上启动 ACE-Step 音乐模型，再开始生成。你的草稿会保留。";
      if(status.model_uncertain&&!processing){
        $("connection").lastElementChild.textContent="需要核实模型状态";
        const resolve=el("button","quiet","已核实模型停止或完成");resolve.type="button";
        resolve.addEventListener("click",async()=>{
          if(!await confirmAction("写词请求的结果不确定。请先确认电脑上的模型已经停止或完成写词，避免同时运行多个任务。确认已核实？"))return;
          resolve.disabled=true;
          try{await api("/api/resolve-model",{method:"POST",body:JSON.stringify({confirmed:true})});await refresh();}
          catch(error){$("create-error").textContent=error.message;resolve.disabled=false;}
        });notice.append(document.createElement("br"),resolve);
      }
      }
    }else{lastStatus="";modelConnected=false;modelProcessing=false;studioState();$("connection").classList.remove("online","working");$("connection").lastElementChild.textContent="连接暂时中断";}
    if(results[1].status==="fulfilled"){renderJobs(results[1].value.jobs||[]);$("library-error").textContent="";}else $("library-error").textContent=results[1].reason.message;
  }finally{pollRunning=false;}
}
$("refresh").addEventListener("click",refresh);
document.addEventListener("visibilitychange",()=>{document.body.classList.toggle("page-hidden",document.hidden);if(!document.hidden)refresh();});
setInterval(()=>{if(!document.hidden)refresh();},5000);
api("/api/session").then(data=>data.authenticated?showWorkspace():showPairing()).catch(()=>{showPairing();$("pair-error").textContent="无法连接工作台，请确认电脑上的启动窗口仍在运行。";});
