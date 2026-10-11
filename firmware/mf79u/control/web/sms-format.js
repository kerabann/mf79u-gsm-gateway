"use strict";

function formatSMSSender(value) {
  const raw=String(value??"").trim();
  if(!raw)return "Unknown sender";
  if(!/^(?:[0-9a-fA-F]{4})+$/.test(raw))return raw;
  // Plain phone numbers can also consist of a multiple of four digits. ZTE's
  // UTF-16BE representation of an ASCII number starts with a 00 code unit.
  if(/^\d+$/.test(raw)&&!raw.startsWith("00"))return raw;
  let decoded="";
  for(let i=0;i<raw.length;i+=4){
    const code=Number.parseInt(raw.slice(i,i+4),16);
    if(!code||code===0xffff||(code<0x20&&code!==0x09))return raw;
    decoded+=String.fromCharCode(code);
  }
  decoded=decoded.trim();
  return decoded||raw;
}

function formatSMSDate(value) {
  const raw=String(value??"").trim();
  if(!raw)return {text:"",dateTime:""};
  const match=raw.match(/^(\d{2}),(\d{1,2}),(\d{1,2}),(\d{1,2}),(\d{1,2}),(\d{1,2}),([+-]?)(\d{1,2})$/);
  if(!match)return {text:raw,dateTime:""};
  const [,shortYear,monthText,dayText,hourText,minuteText,secondText,sign,quarterText]=match;
  const year=Number(shortYear)+(Number(shortYear)>=70?1900:2000);
  const month=Number(monthText),day=Number(dayText),hour=Number(hourText),minute=Number(minuteText),second=Number(secondText),quarters=Number(quarterText);
  const probe=new Date(Date.UTC(year,month-1,day,hour,minute,second));
  if(month<1||month>12||day<1||day>31||hour>23||minute>59||second>59||quarters>56||
    probe.getUTCFullYear()!==year||probe.getUTCMonth()!==month-1||probe.getUTCDate()!==day)return {text:raw,dateTime:""};
  const months=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  const pad=n=>String(n).padStart(2,"0"),offsetHours=Math.floor(quarters/4),offsetMinutes=(quarters%4)*15;
  const offset=`${sign||"+"}${pad(offsetHours)}:${pad(offsetMinutes)}`;
  return {
    text:`${day} ${months[month-1]} ${year}, ${pad(hour)}:${pad(minute)}:${pad(second)} UTC${offset}`,
    dateTime:`${year}-${pad(month)}-${pad(day)}T${pad(hour)}:${pad(minute)}:${pad(second)}${offset}`
  };
}

if(typeof module!=="undefined"&&module.exports)module.exports={formatSMSSender,formatSMSDate};
