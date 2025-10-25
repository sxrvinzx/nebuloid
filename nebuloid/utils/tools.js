import { pem } from '/utils_pem.js';
export let aesKey = null;

export async function api_send(api_name, request_data) {

  // check presence
  if (is_key_present()) {
    const aesKey = await get_key();
  } else {
    try {
    // Generate AES key once
    aesKey = await generateAESKey();
    const aesKeyB64 = await exportAESKey(aesKey);

    // First handshake request
    const request_data = { info: "init_com", key: aesKeyB64 };

    const publicKey = await loadPublicKey(pem);
    const encrypted = await encryptMessage(publicKey, JSON.stringify(request_data));

    // Send to backend
    const response = await fetch('/api', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ data: encrypted })
    });

    const result = await response.json();

    // Decrypt response from backend (expecting { data: "..." })
    const decrypted = await aesDecrypt(aesKey, result);

    console.log("Init response decrypted:", decrypted);

  } catch (error) {
    console.error('Error during init:', error);
  }
  }

  // console.log("Key:", new Uint8Array(await crypto.subtle.exportKey("raw", aesKey)));

  try {
    if (!aesKey) {
      throw new Error("AES key not initialized yet. Run init first.");
    }

    // Prepare request
    // const request_data = { info: "request_data", data : "auth_params"};

    await store_key(aesKey);

    // Encrypt with AES
    const encrypted = await aesEncrypt(aesKey, JSON.stringify(request_data));

    // Send to backend
    const response = await fetch(`/api_${api_name}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ data: encrypted })
    });

    const result = await response.json();

    console.log(`Result fromf /api_${api_name}:`, result, typeof(result));

    if(result?.error ?? null == 'invalid_session') {
      sessionStorage.clear();
      alert("Something went wrong, Please refresh\nError:Session deleted!");
    }

    // Decrypt response
    const decrypted = await aesDecrypt(aesKey, result);

    console.log("Authorize response decrypted:", decrypted);

    return JSON.parse(decrypted);

  } catch (error) {
    console.error("Error in authorize():", error);
  }
}

export async function importAESKey(keyB64) {
  const raw = base64ToArrayBuffer(keyB64); // convert base64 → ArrayBuffer
  return await crypto.subtle.importKey(
    "raw",
    raw,
    { name: "AES-GCM" },
    true,               // extractable
    ["encrypt", "decrypt"]
  );
}

export async function loadPublicKey(pem) {
    // Remove header/footer and newlines
    const b64 = pem.replace(/-----.*?-----|\n/g, '');
    const binaryDer = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
    return await crypto.subtle.importKey(
        "spki", 
        binaryDer.buffer, 
        { name: "RSA-OAEP", hash: "SHA-256" }, 
        true, 
        ["encrypt"]
    );
}

export async function encryptMessage(publicKey, message) {
    const encoder = new TextEncoder();
    const encoded = encoder.encode(message);
    const ciphertext = await crypto.subtle.encrypt(
        { name: "RSA-OAEP" },
        publicKey,
        encoded
    );
    // Convert to base64 for sending
    return btoa(String.fromCharCode(...new Uint8Array(ciphertext)));
}

// Generate a random 256-bit AES-GCM key
export async function generateAESKey() {
  const key = await crypto.subtle.generateKey(
    { name: "AES-GCM", length: 256 },
    true,   // extractable (so we can export for RSA encryption)
    ["encrypt", "decrypt"]
  );
  return key;
}

// Export AES key as raw bytes (to encrypt with RSA later)
export async function exportAESKey(key) {
  const raw = await crypto.subtle.exportKey("raw", key);
  return btoa(String.fromCharCode(...new Uint8Array(raw))); // Base64 for transport
}

// Convert Base64 -> ArrayBuffer
export function base64ToArrayBuffer(b64) {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes.buffer;
}

// Convert ArrayBuffer -> Base64
export function arrayBufferToBase64(buffer) {
  let binary = '';
  const bytes = new Uint8Array(buffer);
  const chunkSize = 0x8000; // process in chunks to avoid stack overflow
  for (let i = 0; i < bytes.length; i += chunkSize) {
    const chunk = bytes.subarray(i, i + chunkSize);
    binary += String.fromCharCode.apply(null, chunk);
  }
  return btoa(binary);
}


// AES Decrypt using AES-GCM
export async function aesDecrypt(aesKey, encrypted) {
  const nonce = base64ToArrayBuffer(encrypted.nonce);
  const ciphertext = base64ToArrayBuffer(encrypted.ciphertext);

  const decrypted = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv: new Uint8Array(nonce) },
    aesKey,
    ciphertext
  );

  return new TextDecoder().decode(decrypted);
}

// AES-GCM Encrypt
export async function aesEncrypt(aesKey, plaintext) {
    // Generate a random nonce (IV)
    const nonce = crypto.getRandomValues(new Uint8Array(12)); // 96-bit recommended for AES-GCM

    const encoded = new TextEncoder().encode(plaintext);

    const ciphertext = await crypto.subtle.encrypt(
        { name: "AES-GCM", iv: nonce },
        aesKey,
        encoded
    );

    return {
        nonce: arrayBufferToBase64(nonce.buffer),
        ciphertext: arrayBufferToBase64(ciphertext)
    };
}

export async function store_key(key) {
  aesKey = key;
  const keyB64 = await exportAESKey(key);
  sessionStorage.setItem("aesKey", keyB64);
}

// --- Retrieve AES key from memory or sessionStorage ---
export async function get_key() {
  if (aesKey) return aesKey;

  const keyB64 = sessionStorage.getItem("aesKey");
  if (!keyB64) return null;

  aesKey = await importAESKey(keyB64);
  return aesKey;
}

// --- Check if AES key exists (memory or sessionStorage) ---
export function is_key_present() {
  return !!aesKey || !!sessionStorage.getItem("aesKey");
}