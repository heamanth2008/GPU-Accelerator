// app.js – shared logic for Neuro Music Glass UI
// This is a trimmed version of the large script from index.html, focusing on core playback, state persistence, and Media Session integration.

/* ==== DATA ==== */
const SONGS = [
    { id:1, title:"Lofi Hip Hop Radio", artist:"Lofi Girl", albumId:3, genre:"Ambient", dur:0, icon:"headphones", grad:"linear-gradient(135deg,#1a1a3e,#4a4aaa)", ytId:"jfKfPfyJRdk" },
    { id:2, title:"On & On", artist:"Cartoon", albumId:1, genre:"Electronic", dur:208, icon:"music", grad:"linear-gradient(135deg,#2d1b69,#11998e)", ytId:"K4DyBUG242c" },
    // … (other songs omitted for brevity) …
];

const ALBUMS = [
    { id:1, name:"NCS Top Hits", artist:"NoCopyrightSounds", icon:"flame", grad:"linear-gradient(135deg,#0f0c29,#302b63,#24243e)", year:2024 },
    { id:3, name:"Lofi Live Streams", artist:"Lofi Girl & Boy", icon:"radio", grad:"linear-gradient(135deg,#093028,#237a57)", year:2024 },
];

const GENRES = [
    { name:"Electronic", icon:"cpu", bg:"linear-gradient(135deg,#4a00e0,#8e2de2)" },
    { name:"Synthwave", icon:"sunset", bg:"linear-gradient(135deg,#f953c6,#b91d73)" },
    // … other genres …
];

/* ==== STATE ==== */
function _migrateLiked(){
    const old = JSON.parse(localStorage.getItem('neuro_liked')||'[]');
    const full = JSON.parse(localStorage.getItem('neuro_liked_songs')||'null');
    if(full!==null) return full;
    return old.map(id=>SONGS.find(s=>s.id===id)).filter(Boolean);
}
function _migratePls(){
    const raw = JSON.parse(localStorage.getItem('neuro_pls')||'[]');
    return raw.map(pl=>({ id: pl.id||('pl_'+Date.now()+Math.random()), name: pl.name, tracks: (pl.ids||[]).map(id=>SONGS.find(s=>s.id===id)).filter(Boolean)}));
}
const S = {
    cur:null, idx:-1, queue:[...SONGS], playing:false, shuffle:false, repeat:false, mute:false, vol:0.7,
    likedSongs:_migrateLiked(), pls:_migratePls(), curPlIdx:-1, view:'home', npOpen:false, playQueue:[]
};
function isLiked(id){return S.likedSongs.some(s=>s.id===id);}

/* ==== YOUTUBE PLAYER ==== */
let ytPlayer=null, ytReady=false, progressInterval=null;
function loadYT(){
    const tag=document.createElement('script'); tag.src='https://www.youtube.com/iframe_api';
    const first=document.getElementsByTagName('script')[0]; first.parentNode.insertBefore(tag,first);
}
function onYouTubeIframeAPIReady(){
    ytPlayer = new YT.Player('yt-player',{height:'0',width:'0',playerVars:{autoplay:0,controls:0,disablekb:1,fs:0,playsinline:1},events:{onReady:onPlayerReady,onStateChange:onPlayerStateChange,onError:onPlayerError}});
}
function onPlayerReady(){ytReady=true; ytPlayer.setVolume(S.vol*100);}
function onPlayerStateChange(e){
    if(e.data===YT.PlayerState.PLAYING){S.playing=true; refreshPlayer(); startProgress();}
    else if(e.data===YT.PlayerState.PAUSED){S.playing=false; refreshPlayer(); stopProgress();}
    else if(e.data===YT.PlayerState.ENDED){ if(!S.repeat) nextTrack(); else {ytPlayer.seekTo(0); ytPlayer.playVideo();}}
}
function onPlayerError(){showToast('Video unavailable'); nextTrack();}

/* ==== PLAYBACK ==== */
function playSong(song,queue){
    if(!ytReady){showToast('Player loading…');return;}
    if(queue) S.queue=queue;
    S.cur=song; S.idx=S.queue.findIndex(t=>t.id===song.id);
    ytPlayer.loadVideoById(song.ytId);
    if(S.mute) ytPlayer.mute(); else ytPlayer.unMute();
    S.playing=true;
    setMediaSession(song);
    refreshPlayer(); refreshHighlights(); renderQueue(); saveState();
    document.title=`${song.title} — Neuro Music`;
}
function togglePlay(){ if(!S.cur||!ytReady)return; S.playing?ytPlayer.pauseVideo():ytPlayer.playVideo(); }
function nextTrack(){ if(!S.queue.length)return; S.idx=S.shuffle?Math.floor(Math.random()*S.queue.length):(S.idx+1)%S.queue.length; playSong(S.queue[S.idx]); }
function prevTrack(){ if(!ytReady)return; if(ytPlayer.getCurrentTime()>3){ytPlayer.seekTo(0);return;} S.idx=(S.idx-1+S.queue.length)%S.queue.length; playSong(S.queue[S.idx]); }
function toggleShuffle(){S.shuffle=!S.shuffle; document.getElementById('shuffle-btn')?.classList.toggle('active',S.shuffle); saveState();}
function toggleRepeat(){S.repeat=!S.repeat; document.getElementById('repeat-btn')?.classList.toggle('active',S.repeat); saveState();}
function toggleMute(){ if(!ytReady)return; S.mute=!S.mute; S.mute?ytPlayer.mute():ytPlayer.unMute(); document.getElementById('vol-btn')?.classList.toggle('muted',S.mute); saveState(); }
function setVol(e){ if(!ytReady)return; const r=document.getElementById('vol-slider').getBoundingClientRect(); const v=Math.max(0,Math.min(1,(e.clientX-r.left)/r.width)); S.vol=v; S.mute=false; ytPlayer.setVolume(v*100); ytPlayer.unMute(); document.getElementById('vol-fill').style.width=v*100+'%'; saveState(); }

/* ==== MEDIA SESSION ==== */
function setMediaSession(song){
    if('mediaSession' in navigator){
        navigator.mediaSession.metadata = new MediaMetadata({
            title: song.title,
            artist: song.artist,
            album: song.album || '',
            artwork: [{src: song.icon?`data:image/svg+xml,<svg ...>`:'',sizes:'512x512',type:'image/svg+xml'}]
        });
        navigator.mediaSession.setActionHandler('play',()=>{if(!S.playing) ytPlayer.playVideo();});
        navigator.mediaSession.setActionHandler('pause',()=>{if(S.playing) ytPlayer.pauseVideo();});
        navigator.mediaSession.setActionHandler('previoustrack',prevTrack);
        navigator.mediaSession.setActionHandler('nexttrack',nextTrack);
    }
}

/* ==== UI REFRESH ==== */
function _artHtml(song){return `<i data-lucide="${song.icon||'music'}" style="width:28px;height:28px;color:#fff;"></i>`;}
function refreshPlayer(){
    const s=S.cur; if(!s)return;
    const art=document.getElementById('player-art'); if(art){art.style.background=s.grad; art.innerHTML=_artHtml(s);}    
    document.getElementById('player-name')?.textContent=s.title;
    document.getElementById('player-artist')?.textContent=s.artist;
    const likeBtn=document.getElementById('player-like'); if(likeBtn){likeBtn.classList.toggle('liked',isLiked(s.id));}
    const pp=document.getElementById('play-pause'); if(pp){const ico=pp.querySelector('i[data-lucide]'); if(ico) ico.setAttribute('data-lucide',S.playing?'pause':'play');}
    refreshMiniPlayer(); lucide.createIcons();
}
function refreshMiniPlayer(){
    const s=S.cur; if(!s)return;
    const mini=document.getElementById('mini-art'); if(mini){mini.style.background=s.grad; mini.innerHTML=_artHtml(s);}    
    document.getElementById('mini-title')?.textContent=s.title;
    document.getElementById('mini-artist')?.textContent=s.artist;
    const ico=document.getElementById('mini-play-ico'); if(ico){ico.setAttribute('data-lucide',S.playing?'pause':'play');}
    lucide.createIcons();
}
function refreshHighlights(){
    document.querySelectorAll('.track-row').forEach(r=>{const playing=parseInt(r.dataset.id)===S.cur?.id; r.classList.toggle('playing',playing);});
}
function renderQueue(){
    const el=document.getElementById('queue-items'); if(!el)return; el.innerHTML=''; const next=S.queue.slice(S.idx+1,S.idx+7); if(!next.length){el.innerHTML='<div style="padding:10px;color:var(--text-muted);">Nothing up next</div>';return;}
    next.forEach(s=>{const d=document.createElement('div'); d.className='playlist-item'; d.onclick=()=>playSong(s); d.innerHTML=`<div class="playlist-thumb" style="background:${s.grad}"><i data-lucide="${s.icon}" style="width:18px;height:18px;color:#fff;"></i></div><div class="playlist-info"><div class="playlist-name">${s.title}</div><div class="playlist-meta">${s.artist}</div></div>`; el.appendChild(d);});
    lucide.createIcons();
}

/* ==== LIKES ==== */
function toggleLike(songOrId,e){if(e) e.stopPropagation(); let song = typeof songOrId==='object'?songOrId:SONGS.find(s=>s.id===songOrId); if(!song) return; const idx=S.likedSongs.findIndex(s=>s.id===song.id); if(idx>=0){S.likedSongs.splice(idx,1); showToast('Removed');} else {S.likedSongs.push(song); showToast('Added');} localStorage.setItem('neuro_liked_songs',JSON.stringify(S.likedSongs)); if(S.view==='liked') renderLiked(); saveState();}
function renderLiked(){ const el=document.getElementById('liked-list'); if(!el)return; const liked=S.likedSongs; el.innerHTML=''; if(!liked.length){el.innerHTML='<div class="empty-state">No liked songs yet.</div>';return;} liked.forEach((s,i)=>{const row=document.createElement('div'); row.className='track-row'; row.dataset.id=s.id; row.onclick=()=>playSong(s); row.innerHTML=`<div class="track-num">${i+1}</div><div class="track-info-cell"><div class="track-art" style="background:${s.grad}"><i data-lucide="${s.icon}" style="width:18px;height:18px;"></i></div><div class="track-text"><div class="track-title">${s.title}</div><div class="track-artist">${s.artist}</div></div></div><button class="like-btn" onclick="toggleLike(${s.id},event)">♥</button>`; el.appendChild(row);}); lucide.createIcons();}

/* ==== THEME ==== */
function initTheme(){ const t=localStorage.getItem('neuro_theme')||'dark'; document.documentElement.setAttribute('data-theme',t); updateThemeIcon(t);} 
function toggleTheme(){ const cur=document.documentElement.getAttribute('data-theme')||'dark'; const next=cur==='dark'?'light':'dark'; document.documentElement.setAttribute('data-theme',next); localStorage.setItem('neuro_theme',next); updateThemeIcon(next);} 
function updateThemeIcon(theme){ const btn=document.getElementById('theme-toggle-btn'); if(btn){const ico=btn.querySelector('i[data-lucide]'); if(ico){ico.setAttribute('data-lucide',theme==='dark'?'sun':'moon'); lucide.createIcons({nodes:[ico]});}}}

/* ==== STATE PERSISTENCE ==== */
const STATE_KEY='neuro_player_state';
function saveState(){ try{ const snap={ytId:S.cur?.ytId||null,trackId:S.cur?.id||null,title:S.cur?.title||null,artist:S.cur?.artist||null,grad:S.cur?.grad||null,icon:S.cur?.icon||'music',vol:S.vol,shuffle:S.shuffle,repeat:S.repeat}; localStorage.setItem(STATE_KEY,JSON.stringify(snap)); localStorage.setItem('neuro_liked_songs',JSON.stringify(S.likedSongs)); localStorage.setItem('neuro_pls',JSON.stringify(S.pls)); }catch(e){} }
function restoreState(){ try{ const snap=JSON.parse(localStorage.getItem(STATE_KEY)); if(!snap) return; S.vol=snap.vol??0.7; S.shuffle=snap.shuffle??false; S.repeat=snap.repeat??false; if(snap.ytId){ S.cur={id:snap.trackId,ytId:snap.ytId,title:snap.title,artist:snap.artist,grad:snap.grad,icon:snap.icon||'music'}; refreshPlayer(); refreshMiniPlayer(); } }catch(e){} }

/* ==== INIT ==== */
(function(){
  initTheme();
  loadYT();
  restoreState();
  lucide.createIcons();

  // Keep playback when page is hidden (mobile background)
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      // If audio is playing, ensure it stays playing
      if (S.playing && ytPlayer) {
        ytPlayer.playVideo();
      }
    }
  });
})();
