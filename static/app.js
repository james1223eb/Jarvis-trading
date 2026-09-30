async function api(url, opts={}) {
  const r=await fetch(url,{headers:{"Content-Type":"application/json"},...opts});
  return await r.json();
}
function showPage(id){
  document.querySelectorAll(".page").forEach(p=>p.classList.remove("active"));
  document.getElementById(id).classList.add("active");
  if(id==="dashboard") loadPortfolio();
  if(id==="community") loadPosts();
}
async function login(){
  const username=prompt("Choose a username");
  if(!username)return;
  const r=await api("/api/login",{method:"POST",body:JSON.stringify({username})});
  alert(r.ok ? "Logged in as "+username : r.error);
  if(r.ok) loadPortfolio();
}
async function loadPortfolio(){
  const r=await api("/api/portfolio");
  if(r.error)return;
  document.getElementById("total").textContent="$"+r.total.toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2});
  document.getElementById("cash").textContent="$"+r.cash.toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2});
  document.getElementById("count").textContent=r.positions.length;
  let html="<table><tr><th>Symbol</th><th>Shares</th><th>Avg</th><th>Price</th><th>P/L</th></tr>";
  for(const p of r.positions)
    html+=`<tr><td>${p.symbol}</td><td>${p.shares}</td><td>$${p.avg_price.toFixed(2)}</td><td>$${p.price.toFixed(2)}</td><td>$${p.pnl.toFixed(2)}</td></tr>`;
  document.getElementById("positions").innerHTML=html+"</table>";
}
async function quote(){
  const s=document.getElementById("marketSymbol").value.trim();
  const r=await api("/api/quote/"+encodeURIComponent(s));
  document.getElementById("quoteBox").innerHTML=r.error?`<b>${r.error}</b>`:
    `<h2>${r.symbol}</h2><strong style="font-size:32px">$${r.price.toFixed(2)}</strong><p>Market data is supplied through yfinance in this prototype.</p>`;
}
async function trade(side){
  const symbol=document.getElementById("tradeSymbol").value.trim();
  const shares=document.getElementById("tradeShares").value;
  const r=await api("/api/trade",{method:"POST",body:JSON.stringify({symbol,shares,side})});
  document.getElementById("tradeMsg").innerHTML=r.error?`<p style="color:#ff7b88">${r.error}</p>`:
    `<p style="color:#7be0b4">${side} completed at $${r.price.toFixed(2)}</p>`;
  loadPortfolio();
}
async function askJarvis(){
  const q=document.getElementById("question").value.trim(); if(!q)return;
  const chat=document.getElementById("chat");
  chat.innerHTML+=`<div class="user">${safe(q)}</div>`;
  document.getElementById("question").value="";
  const r=await api("/api/jarvis",{method:"POST",body:JSON.stringify({message:q})});
  chat.innerHTML+=`<div class="jarvis">${safe(r.answer||r.error)}</div>`;
}
async function post(){
  const body=document.getElementById("post").value.trim(); if(!body)return;
  const r=await api("/api/community",{method:"POST",body:JSON.stringify({body})});
  if(r.error){alert(r.error);return}
  document.getElementById("post").value="";
  loadPosts();
}
async function loadPosts(){
  const posts=await api("/api/community");
  document.getElementById("posts").innerHTML=posts.map(p=>
    `<div class="post"><b>${safe(p.username)}</b><p>${safe(p.body)}</p><small>${p.created_at}</small></div>`
  ).join("");
}
function safe(s){return String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",""":"&quot;","'":"&#039;"}[c]))}
loadPortfolio();
