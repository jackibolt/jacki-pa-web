from app import create_app
from dotenv import load_dotenv

# Create the Flask app instance
load_dotenv()
app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host='127.0.0.1', port=5501)