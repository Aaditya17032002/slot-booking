# Firefox userscript monitor (Android / desktop)

Runs **inside real Firefox** where you already logged in — no Playwright, no Azure.

## Install (Firefox Android)

1. Install **Firefox** from the Play Store  
2. In Firefox → Settings → **About Firefox** → tap the logo 5+ times to enable secret settings  
3. Settings → **Add-ons** → find and install **Tampermonkey** or **Violentmonkey**  
4. Open this file on the phone (GitHub raw, Drive, or copy-paste):
   - `userscript/usvisa-slot-monitor.user.js`  
5. Tampermonkey → **+** / Install from URL or paste the script → **Install**  
6. Edit the script → set at the top:

```js
TELEGRAM_BOT_TOKEN: "your_token",
TELEGRAM_CHAT_ID: "your_chat_id",
```

(Use the same values as in your PC `.env`.)

## Use

1. In Firefox, open https://www.usvisascheduling.com and **log in yourself** (pass Cloudflare)  
2. Go to the **schedule / appointment** page (where Kolkata/Mumbai VAC dropdown appears)  
3. You should see a dark **US Visa monitor** panel (bottom-right)  
4. Tap **Test Telegram** once  
5. Leave Firefox open on that tab (screen can stay on). The script reloads every ~3–7 minutes  

## Tips

- Keep the appointment tab in the foreground when possible  
- If Telegram says Cloudflare/login — unlock phone, fix it in Firefox, leave the tab open  
- **Book manually** when you get a “NEW SLOT” alert  
- Do not publish the script with your bot token in a public place  

## Desktop Firefox

Same script works on desktop Firefox with Tampermonkey — useful for testing before Android.
