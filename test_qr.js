const { Client, LocalAuth } = require('whatsapp-web.js')
const qrcode = require('qrcode-terminal')

const client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: {
        executablePath: '/usr/bin/chromium-browser',
        args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
        timeout: 60000
    }
})

client.on('qr', qr => {
    console.log('QR recibido, escanealo:')
    qrcode.generate(qr, { small: true })
})

client.on('ready', () => {
    console.log('Bot conectado!')
})

client.initialize()
