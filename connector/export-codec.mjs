/** Decode the downloaded HTML using its declared encoding, never replacement glyphs. */
export function decodeExport(bytes){
  const prefix=bytes.subarray(0,4096).toString('latin1');
  const declared=prefix.match(/charset\s*=\s*["']?([\w-]+)/i)?.[1]?.toLowerCase();
  let encoding=bytes[0]===0xff&&bytes[1]===0xfe?'utf-16le':bytes[0]===0xfe&&bytes[1]===0xff?'utf-16be':declared;
  const allowed=new Set(['utf-8','utf8','utf-16','utf-16le','utf-16be','windows-1252','iso-8859-1']);
  if(encoding&&!allowed.has(encoding))throw Error('export-encoding');
  if(encoding)return new TextDecoder(encoding,{fatal:true}).decode(bytes);
  try{return new TextDecoder('utf-8',{fatal:true}).decode(bytes);}
  catch{return new TextDecoder('windows-1252',{fatal:true}).decode(bytes);}
}
