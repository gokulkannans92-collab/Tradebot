import os
import secrets
import webbrowser
from flask import Flask, request
from upstox_client.rest import ApiException
import urllib.parse
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

UPSTOX_API_KEY = os.getenv("UPSTOX_API_KEY")
UPSTOX_API_SECRET = os.getenv("UPSTOX_API_SECRET")
REDIRECT_URI = "http://localhost:8000/"

@app.route("/")
def callback():
    code = request.args.get("code")
    if not code:
        return "No authorization code provided in URL.", 400

    try:
        import requests
        
        url = 'https://api.upstox.com/v2/login/authorization/token'
        headers = {
            'accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        
        data = {
            'code': code,
            'client_id': UPSTOX_API_KEY,
            'client_secret': UPSTOX_API_SECRET,
            'redirect_uri': REDIRECT_URI,
            'grant_type': 'authorization_code'
        }
        
        response = requests.post(url, headers=headers, data=data)
        if response.status_code == 200:
            token = response.json().get('access_token')
            
            # Save the new token back to .env
            env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env")
            if os.path.exists(env_path):
                with open(env_path, 'r', encoding="utf-8") as f:
                    lines = f.readlines()
                
                with open(env_path, 'w', encoding="utf-8") as f:
                    for line in lines:
                        if line.startswith('UPSTOX_ACCESS_TOKEN='):
                            f.write(f'UPSTOX_ACCESS_TOKEN={token}\n')
                        else:
                            f.write(line)
                            
            return f"""
            <h2>Authentication Successful! ✅</h2>
            <p>Your new UPSTOX_ACCESS_TOKEN has been generated.</p>
            <p><strong>Code has automatically saved it to your .env file!</strong></p>
            <p>You can now close this tab, stop this script in your terminal, and run your TradeBot.</p>
            """, 200
        else:
            return f"❌ Failed to get token: {response.text}", response.status_code

    except Exception as e:
        return f"❌ Error: {str(e)}", 500

def get_login_url():
    """Generate the login URL for Upstox OAuth2"""
    auth_url = "https://api.upstox.com/v2/login/authorization/dialog"
    params = {
        "response_type": "code",
        "client_id": UPSTOX_API_KEY,
        "redirect_uri": REDIRECT_URI
    }
    return f"{auth_url}?{urllib.parse.urlencode(params)}"

if __name__ == "__main__":
    if not UPSTOX_API_KEY or not UPSTOX_API_SECRET:
        print("❌ UPSTOX_API_KEY or UPSTOX_API_SECRET missing from .env file!")
        exit(1)
        
    login_url = get_login_url()
    print("=" * 60)
    print("🚀 UPSTOX AUTHENTICATION SERVER")
    print("=" * 60)
    print(f"Opening browser to authenticate...")
    print(f"If browser doesn't open, click this link:\n{login_url}")
    print("=" * 60)
    
    # Give the server a second to start before opening browser
    import threading, time
    def open_browser():
        time.sleep(1.5)
        webbrowser.open(login_url)
        
    threading.Thread(target=open_browser).start()
    
    # Start local server on port 8000
    app.run(host="localhost", port=8000)
