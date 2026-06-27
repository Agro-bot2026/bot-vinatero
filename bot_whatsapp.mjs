import makeWASocket, {
    useMultiFileAuthState,
    DisconnectReason,
    fetchLatestBaileysVersion,
    Browsers,
    downloadMediaMessage
} from '@whiskeysockets/baileys'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import pino from 'pino'
import { GoogleGenerativeAI } from "@google/generative-ai"
const genai = new GoogleGenerativeAI("AIzaSyAzPGVc4RdvmHqyF5G74BUtvekYnTQW4a0")
import qrcode from 'qrcode-terminal'
import fs from 'fs'
import net from 'net'
import { execSync } from 'child_process'
import os from 'os'
import path from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

// ============================================================
// CONFIGURACION
// ============================================================
const ADMIN_NUMBER = '210101847752834@lid'
const ARCHIVO_USUARIOS = join(__dirname, 'usuarios_autorizados.json')
const SOCKET_PATH = '/tmp/gemini_bot.sock'

// ============================================================
// SISTEMA DE USUARIOS
// ============================================================
function cargarUsuarios() {
    if (fs.existsSync(ARCHIVO_USUARIOS)) {
        try { return JSON.parse(fs.readFileSync(ARCHIVO_USUARIOS, 'utf8')) } catch {}
    }
    return { autorizados: [ADMIN_NUMBER], pendientes: {}, bloqueados: [] }
}

function guardarUsuarios(datos) {
    fs.writeFileSync(ARCHIVO_USUARIOS, JSON.stringify(datos, null, 2))
}

function esAutorizado(jid) { return cargarUsuarios().autorizados.includes(jid) }
function esBloqueado(jid) { return (cargarUsuarios().bloqueados || []).includes(jid) }
function estaPendiente(jid) { return jid in cargarUsuarios().pendientes }

function agregarPendiente(jid, nombre) {
    const datos = cargarUsuarios()
    datos.pendientes[jid] = { nombre, fecha: new Date().toLocaleString('es-AR') }
    guardarUsuarios(datos)
}

function autorizarUsuario(jid) {
    const datos = cargarUsuarios()
    if (!datos.autorizados.includes(jid)) datos.autorizados.push(jid)
    delete datos.pendientes[jid]
    guardarUsuarios(datos)
}

function rechazarUsuario(jid) {
    const datos = cargarUsuarios()
    delete datos.pendientes[jid]
    guardarUsuarios(datos)
}

function bloquearUsuario(jid) {
    const datos = cargarUsuarios()
    if (!datos.bloqueados) datos.bloqueados = []
    if (!datos.bloqueados.includes(jid)) datos.bloqueados.push(jid)
    datos.autorizados = datos.autorizados.filter(u => u !== jid)
    delete datos.pendientes[jid]
    guardarUsuarios(datos)
}

// ============================================================
// MEMORIA CONVERSACIONAL
// ============================================================
const historial = {}
const MAX_TURNOS = 15

function obtenerHistorial(jid) { return historial[jid] || [] }

function agregarHistorial(jid, role, texto) {
    if (!historial[jid]) historial[jid] = []
    historial[jid].push({ role, texto })
    if (historial[jid].length > MAX_TURNOS * 2)
        historial[jid] = historial[jid].slice(-(MAX_TURNOS * 2))
}

function limpiarHistorial(jid) { delete historial[jid] }

function construirContexto(jid) {
    const h = obtenerHistorial(jid)
    if (!h.length) return ''
    let ctx = 'HISTORIAL DE CONVERSACION ANTERIOR:\n'
    for (const t of h)
        ctx += `${t.role === 'user' ? 'Usuario' : 'Asistente'}: ${t.texto}\n`
    return ctx + '\n'
}

// ============================================================
// CONSULTA AL SERVIDOR PYTHON VIA SOCKET
// ============================================================
async function consultarGemini(jid, texto, imagenPath = null) {
    return new Promise((resolve, reject) => {
        const contexto = construirContexto(jid)
        const payload = JSON.stringify({ texto, contexto, imagenPath: imagenPath || '', userId: jid }) + '\n'

        const client = net.createConnection(SOCKET_PATH, () => {
            client.write(payload)
        })

        let respuesta = ''
        client.on('data', d => respuesta += d.toString())
        client.on('end', () => {
            try { resolve(JSON.parse(respuesta.trim())) }
            catch { reject(new Error('Error parseando respuesta')) }
        })
        client.on('error', reject)
        client.setTimeout(120000, () => {
            client.destroy()
            reject(new Error('Timeout'))
        })
    })
}

// ============================================================
// BOT WHATSAPP
// ============================================================
async function startSock() {
    const { state, saveCreds } = await useMultiFileAuthState(join(__dirname, 'auth_info'))
    const { version } = await fetchLatestBaileysVersion()
    const logger = pino({ level: 'silent' })

    const sock = makeWASocket({
        version,
        logger,
        printQRInTerminal: false,
        auth: state,
        browser: Browsers.ubuntu('Chrome'),
    })

    sock.ev.on('connection.update', async (update) => {
        const { connection, lastDisconnect, qr } = update

        if (qr) {
            console.log('\n📱 Escanea este QR con WhatsApp del numero del bot:\n')
            qrcode.generate(qr, { small: true })
        }

        if (connection === 'close') {
            const shouldReconnect = lastDisconnect?.error?.output?.statusCode !== DisconnectReason.loggedOut
            console.log('Conexion cerrada. Reconectando:', shouldReconnect)
            if (shouldReconnect) startSock()
        }

        if (connection === 'open') console.log('✅ Bot conectado a WhatsApp!')
    })

    sock.ev.on('creds.update', saveCreds)

    sock.ev.on('messages.upsert', async ({ messages }) => {
        for (const msg of messages) {
            if (msg.key.fromMe) continue
            if (!msg.message) continue

            const jid = msg.key.remoteJid
            const textoMsg = msg.message?.conversation ||
                msg.message?.extendedTextMessage?.text ||
                msg.message?.imageMessage?.caption || ''

            const nombreUsuario = msg.pushName || 'Usuario'
            const tieneAudio = !!(msg.message?.audioMessage)
            const audioMsg = msg.message?.audioMessage
            const tieneImagen = !!(msg.message?.imageMessage)
            const esComandoImagen = tieneImagen && (
                textoMsg.toLowerCase().includes('/plaga') ||
                textoMsg.toLowerCase().includes('/escanear')
            )

            if (tieneImagen && !esComandoImagen) continue
            const tieneUbicacion = !!(msg.message?.locationMessage)
            if (!textoMsg && !tieneImagen && !tieneAudio && !tieneUbicacion) continue
            if (esBloqueado(jid)) continue

            if (!esAutorizado(jid)) {
                if (estaPendiente(jid)) {
                    await sock.sendMessage(jid, { text: '⏳ Tu solicitud ya esta pendiente. Te avisamos cuando seas aprobado.' })
                    continue
                }
                agregarPendiente(jid, nombreUsuario)
                await sock.sendMessage(jid, {
                    text: '🔒 Acceso restringido.\n\nEste bot es exclusivo para contratistas de vinas autorizados.\nTu solicitud fue enviada al administrador.'
                })
                await sock.sendMessage(ADMIN_NUMBER, {
                    text: `🔔 Nueva solicitud de acceso\n\nNombre: ${nombreUsuario}\nJID: ${jid}\nFecha: ${new Date().toLocaleString('es-AR')}\n\nResponde con:\n✅ /autorizar ${jid}\n❌ /rechazar ${jid}`
                })
                continue
            }

            // Comandos admin
            if (textoMsg.startsWith('/autorizar ')) {
                const uid = textoMsg.split(' ')[1]
                autorizarUsuario(uid)
                await sock.sendMessage(jid, { text: `✅ Usuario autorizado.` })
                try { await sock.sendMessage(uid, { text: '✅ Tu acceso fue aprobado! Escribi *hola* para comenzar.' }) } catch {}
                continue
            }
            if (textoMsg.startsWith('/rechazar ')) {
                rechazarUsuario(textoMsg.split(' ')[1])
                await sock.sendMessage(jid, { text: `❌ Usuario rechazado.` })
                continue
            }
            if (textoMsg.startsWith('/bloquear ')) {
                bloquearUsuario(textoMsg.split(' ')[1])
                await sock.sendMessage(jid, { text: `🚫 Usuario bloqueado.` })
                continue
            }
            if (textoMsg === '/usuarios') {
                const datos = cargarUsuarios()
                let texto = `👥 Usuarios del bot\n\nAutorizados: ${datos.autorizados.length}\nPendientes: ${Object.keys(datos.pendientes).length}\nBloqueados: ${(datos.bloqueados||[]).length}`
                if (Object.keys(datos.pendientes).length) {
                    texto += '\n\nPendientes:\n'
                    for (const [uid, info] of Object.entries(datos.pendientes))
                        texto += `- ${info.nombre} | ${uid}\n`
                }
                await sock.sendMessage(jid, { text: texto })
                continue
            }

            // Comandos generales
            if (textoMsg === '/clima') {
                await sock.sendMessage(jid, { 
                    text: 'Compartí tu ubicacion de WhatsApp para ver el clima de tu zona.' 
                })
                continue
            }
            if (msg.message?.locationMessage) {
                const lat = msg.message.locationMessage.degreesLatitude
                const lon = msg.message.locationMessage.degreesLongitude
                await sock.sendPresenceUpdate('composing', jid)
                const payload = JSON.stringify({ tipo: 'clima', lat, lon }) + '\n'
                const climaResp = await new Promise((resolve, reject) => {
                    const client = net.createConnection('/tmp/gemini_bot.sock', () => client.write(payload))
                    let resp = ''
                    client.on('data', d => resp += d.toString())
                    client.on('end', () => { try { resolve(JSON.parse(resp.trim())) } catch { reject(new Error('Parse error')) } })
                    client.on('error', reject)
                    client.setTimeout(30000, () => { client.destroy(); reject(new Error('Timeout')) })
                })
                await sock.sendMessage(jid, { text: climaResp.texto })
                continue
            }
            if (textoMsg === '/informe') {
                const hist = obtenerHistorial(jid)
                if (!hist || hist.length < 2) {
                    await sock.sendMessage(jid, { text: '📋 No hay consulta para generar informe.\n\nUsá */nuevo* para empezar una consulta, hacé tus preguntas o mandá fotos, y al terminar escribí */informe*.' })
                    continue
                }
                await sock.sendMessage(jid, { text: '⏳ Generando informe PDF...' })
                try {
                    const resumen = hist.map(h => '[' + (h.role === 'user' ? 'Consulta' : 'Respuesta') + ']: ' + h.texto).join('\n\n')
                    const payload = JSON.stringify({ 
                        tipo: 'informe', 
                        diagnostico: resumen,
                        imagenPath: '',
                        nombre: nombreUsuario 
                    }) + '\n'
                    const respuesta = await new Promise((resolve, reject) => {
                        const chunks = []
                        const client = net.createConnection(SOCKET_PATH, () => client.write(payload))
                        client.on('data', d => chunks.push(d))
                        client.on('end', () => resolve(Buffer.concat(chunks).toString()))
                        client.on('error', reject)
                        setTimeout(() => reject(new Error('timeout')), 30000)
                    })
                    const data = JSON.parse(respuesta.trim())
                    if (data.error) throw new Error(data.error)
                    const pdfBuffer = Buffer.from(data.pdf, 'base64')
                    await sock.sendMessage(jid, {
                        document: pdfBuffer,
                        mimetype: 'application/pdf',
                        fileName: 'Informe_Agronomico.pdf',
                        caption: '📋 *Informe Técnico Agronómico*\nBot Experto en Viñedos · INTA · INV\n\nListo para enviar al ingeniero agrónomo. 🌿'
                    })
                } catch (e) {
                    await sock.sendMessage(jid, { text: '❌ Error generando informe: ' + e.message })
                }
                continue
            }
            // Comando /podcast
            if (textoMsg.toLowerCase().startsWith('/podcast')) {
                const tema = textoMsg.replace('/podcast', '').trim()
                if (!tema) {
                    await sock.sendMessage(jid, { text: '🎙️ Indicá el tema del podcast.\n\nEjemplos:\n• /podcast oídio en moscatel\n• /podcast poda en espaldera\n• /podcast riego post cosecha' })
                    return
                }
                await sock.sendMessage(jid, { text: '🎙️ Generando podcast sobre "' + tema + '"...\nEsto puede tardar unos segundos.' })
                try {
                    const payload = JSON.stringify({ tipo: 'podcast', tema }) + '\n'
                    const respuesta = await new Promise((resolve, reject) => {
                        const chunks = []
                        const client = net.createConnection(SOCKET_PATH, () => client.write(payload))
                        client.on('data', d => chunks.push(d))
                        client.on('end', () => resolve(Buffer.concat(chunks).toString()))
                        client.on('error', reject)
                        setTimeout(() => reject(new Error('timeout')), 150000)
                    })
                    const data = JSON.parse(respuesta.trim())
                    if (data.error) throw new Error(data.error)
                    const audioBuffer = Buffer.from(data.audio, 'base64')
                    await sock.sendMessage(jid, {
                        audio: audioBuffer,
                        mimetype: 'audio/ogg; codecs=opus',
                        ptt: true
                    })
                } catch (e) {
                    await sock.sendMessage(jid, { text: '❌ Error: ' + e.message })
                }
                return
            }
            if (textoMsg === '/nuevo' || textoMsg.toLowerCase() === 'nuevo') {
                limpiarHistorial(jid)
                await sock.sendMessage(jid, { 
                    text: '🔄 *Conversación reiniciada*\n\nPodés empezar una consulta nueva.\n\n📸 Para analizar una planta:\n• Foto + */plaga* → busca enfermedades\n• Foto + */plaga moscatel* → con variedad\n• Foto + */escanear* → diagnóstico general\n• Foto + */escanear envero disparejo* → con comentario\n\nAl terminar escribí */informe* para recibir el PDF. 📋'
                })
                continue
            }

            if (['/ayuda', '/start', 'hola', 'ayuda'].includes(textoMsg.toLowerCase())) {
                await sock.sendMessage(jid, {
                    text: `Hola ${nombreUsuario}! 🍇\n\nSoy tu *Experto en Viñedos* con IA especializada en viticultura de Cuyo.\n\nPuedo ayudarte con:\n🌿 Enfermedades y plagas de la vid\n💧 Riego y nutricion\n✂️ Poda y conduccion\n🧪 Tratamientos fitosanitarios con dosis exactas\n🍇 Identificacion de variedades\n\n*Como usarme:*\n• Escribime tu consulta directamente\n• Foto + */plaga* → analiza enfermedades y plagas\n• Foto + */plaga moscatel* → con variedad o comentario\n• Foto + */escanear* → diagnóstico general de la planta\n• Foto + */escanear envero disparejo* → con comentario\n• */nuevo* → nueva consulta y limpia el historial\n• */informe* → genera PDF de la consulta para el ingeniero\n• */podcast [tema]* → genera audio con dos voces sobre el tema\n• */ayuda* → ver este mensaje\n\nTe respondo siempre en audio! 🎙️`
                })
                continue
            }

            // Transcribir audio si es mensaje de voz
            let textoFinal = textoMsg
            if (tieneAudio && !textoMsg) {
                try {
                    await sock.sendPresenceUpdate("composing", jid)
                    const audioBuffer = await downloadMediaMessage(msg, "buffer", {})
                    const audioB64 = audioBuffer.toString("base64")
                    const resultadoAudio = await new Promise((resolve, reject) => {
                        const payload = JSON.stringify({ tipo: "audio", audio: audioB64 }) + "\n"
                        const client = net.createConnection("/tmp/gemini_bot.sock", () => client.write(payload))
                        let resp = ""
                        client.on("data", d => resp += d.toString())
                        client.on("end", () => { try { resolve(JSON.parse(resp.trim())) } catch { reject(new Error("Parse error")) } })
                        client.on("error", reject)
                        client.setTimeout(60000, () => { client.destroy(); reject(new Error("Timeout")) })
                    })
                    textoFinal = resultadoAudio.texto.trim()
                    if (!textoFinal) { await sock.sendMessage(jid, { text: "No pude entender el audio. Por favor escribi tu consulta." }); continue }
                } catch (e) {
                    console.error("ERROR AUDIO:", e.message)
                    await sock.sendMessage(jid, { text: "No pude procesar el audio. Por favor escribi tu consulta." })
                    continue
                }
            }
            // Procesar consulta
            try {
                await sock.sendPresenceUpdate('recording', jid)

                let imagenPath = null
                if (esComandoImagen) {
                    const buffer = await downloadMediaMessage(msg, 'buffer', {})
                    imagenPath = `/tmp/img_${Date.now()}.jpg`
                    fs.writeFileSync(imagenPath, buffer)
                }

                const comentarioExtra = textoFinal.replace('/plaga', '').replace('/escanear', '').trim()
                const contextoUsuario = comentarioExtra ? `El contratista indica: "${comentarioExtra}". ` : ''
                const consultaFinal = esComandoImagen
                    ? textoFinal.toLowerCase().includes('/plaga')
                        ? `${contextoUsuario}Analizá esta imagen buscando plagas, enfermedades o problemas fitosanitarios en la vid. Describí síntomas detectados, causa probable y tratamiento recomendado con dosis exactas.`
                        : `${contextoUsuario}Analizá esta imagen de la planta en detalle. Identificá variedad si es posible, estado fenológico, condición general y cualquier problema que observes.`
                    : textoFinal

                const resultado = await consultarGemini(jid, consultaFinal, imagenPath)

                if (imagenPath && fs.existsSync(imagenPath)) fs.unlinkSync(imagenPath)

                agregarHistorial(jid, 'user', consultaFinal)
                agregarHistorial(jid, 'assistant', resultado.texto)

                if (resultado.audio) {
                    const audioBuffer = Buffer.from(resultado.audio, 'base64')
                    // Convertir MP3 a OGG/OPUS para WhatsApp
                    let finalBuffer = audioBuffer
                    let finalMime = 'audio/ogg; codecs=opus'
                    try {
                        const tmpMp3 = path.join(os.tmpdir(), `audio_${Date.now()}.mp3`)
                        const tmpOgg = path.join(os.tmpdir(), `audio_${Date.now()}.ogg`)
                        fs.writeFileSync(tmpMp3, audioBuffer)
                        execSync(`ffmpeg -i ${tmpMp3} -c:a libopus -b:a 64k ${tmpOgg} -y 2>/dev/null`)
                        finalBuffer = fs.readFileSync(tmpOgg)
                        fs.unlinkSync(tmpMp3)
                        fs.unlinkSync(tmpOgg)
                    } catch(e) {
                        console.error('ffmpeg error, usando MP3:', e.message)
                        finalMime = 'audio/mpeg'
                    }
                    await sock.sendMessage(jid, {
                        audio: finalBuffer,
                        mimetype: finalMime,
                        ptt: true
                    })
                } else {
                    await sock.sendMessage(jid, { text: resultado.texto })
                }

            } catch (err) {
                console.error('Error:', err)
                await sock.sendMessage(jid, { text: '❌ Ocurrio un error. Intenta de nuevo.' })
            }
        }
    })
}

startSock().catch(err => console.error('Error al iniciar:', err))

process.on('SIGINT', () => {
    console.log('Cerrando bot...')
    process.exit(0)
})
