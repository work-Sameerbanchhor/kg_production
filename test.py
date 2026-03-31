import requests
import os

# Your Mac's network IP and Port
IP_ADDRESS = "10.218.130.133"  
PORT = 52002
URL = f"http://{IP_ADDRESS}:{PORT}/api/upload-pdf"

# Create a temporary dummy PDF file to test with
dummy_file_path = "test_document.pdf"
with open(dummy_file_path, "wb") as f:
    f.write(b"%PDF-1.4\n%This is a dummy PDF for testing\n")

print(f"🚀 Attempting to upload to: {URL}")

try:
    # Open the file and send the POST request
    with open(dummy_file_path, "rb") as f:
        # The key 'file' must match the parameter name in your FastAPI endpoint
        files = {"file": (dummy_file_path, f, "application/pdf")}
        response = requests.post(URL, files=files, timeout=10)

    print(f"\n📡 Status Code: {response.status_code}")
    print(f"📨 Response text: {response.text}")

    if response.status_code == 200:
        print("\n✅ SUCCESS! The server is perfectly fine and accepting files over the network.")
    else:
        print("\n❌ FAILED. The server was reached, but it rejected the file.")

except requests.exceptions.ConnectionError:
    print("\n❌ CONNECTION ERROR: Could not reach the server at all.")
    print("👉 FIX: Check your Mac's System Settings > Network > Firewall. It might be blocking port 52002.")
except Exception as e:
    print(f"\n❌ UNEXPECTED ERROR: {e}")
finally:
    # Clean up the dummy file
    if os.path.exists(dummy_file_path):
        os.remove(dummy_file_path)