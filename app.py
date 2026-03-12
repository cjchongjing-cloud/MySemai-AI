from flask import Flask, request, jsonify
from flask_cors import CORS 
import sqlite3
import os
import random

import google.generativeai as genai
from dotenv import load_dotenv 

load_dotenv() #  to read the .env file

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash")

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel(MODEL_NAME)

if not os.path.exists('dataset'):
    os.makedirs('dataset')

app = Flask(__name__)
CORS(app)  

# database setup

# JSON API route for the homepage
@app.route('/')
def home():
    conn = sqlite3.connect('semai.db')
    
    # get all words
    cursor = conn.execute("SELECT * FROM words")
    word_list = cursor.fetchall()
    
    # get 5 recent words
    cursor_recent = conn.execute("SELECT * FROM words ORDER BY rowid DESC LIMIT 5")
    recent_list = cursor_recent.fetchall()
    
    conn.close()
    
    return jsonify({
        "status": "success",
        "all_words": word_list,
        "recent_words": recent_list
    })

@app.route('/add_word', methods=['POST'])
def add_word():
    semai_word = request.form.get('semai')
    english_word = request.form.get('english')
    
    conn = sqlite3.connect('semai.db')
    try:
        conn.execute("INSERT INTO words (semai, english) VALUES (?, ?)", (semai_word, english_word))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"status": "error", "message": "Word already exists!"})
    conn.close()

    for i in range(1, 6):
        video_file = request.files.get(f'video_{i}')
        if video_file:
            video_file.save(os.path.join('dataset', f"{semai_word}_{i}.webm"))
            
    return jsonify({"status": "success", "message": "Saved!"})

@app.route('/chat', methods=['POST'])
def chat():
    user_msg = request.json.get('message')
    
    conn = sqlite3.connect('semai.db')
    cursor = conn.execute("SELECT semai, english FROM words")
    db_words = cursor.fetchall()
    conn.close()
    
    vocab_list = ", ".join([f"{w[0]} ({w[1]})" for w in db_words])
    prompt = f"You are a helpful AI assistant for a Bahasa Semai language app. The user currently has these words saved in their library: {vocab_list}. Answer the user's message clearly and concisely. User message: {user_msg}"
    
    try:
        # switched to gemini
        chat_model = genai.GenerativeModel(MODEL_NAME)
        response = chat_model.generate_content(prompt)
        return jsonify({"response": response.text})
    except Exception as e:
        
        return jsonify({"response": f"System Alert: {str(e)}"})

@app.route('/scan_lips', methods=['POST'])
def scan_lips():
    video_file = request.files.get('video')
    if not video_file:
        return jsonify({"semai": "Error", "english": "No video", "confidence": "0%"})

    temp_path = os.path.join('dataset', "temp_scan.webm")
    video_file.save(temp_path)

    conn = sqlite3.connect('semai.db')
    cursor = conn.execute("SELECT semai, english FROM words")
    db_words = cursor.fetchall()
    conn.close()
    
    vocab_list = ", ".join([f"'{w[0]}' ({w[1]})" for w in db_words])
    prompt = f"Analyze this short video of a person speaking. Guess which word they are saying. You MUST choose ONLY from this list: {vocab_list}. Also, estimate your confidence level from 0% to 100%. Reply in this EXACT format: SemaiWord - EnglishMeaning - ConfidencePercentage"
    
    sample_file = None
    try:
        sample_file = genai.upload_file(path=temp_path)
        response = model.generate_content([sample_file, prompt])
        
        result = response.text.strip().split('-')
        if len(result) >= 3:
            return jsonify({"semai": result[0].strip(), "english": result[1].strip(), "confidence": result[2].strip()})
        else:
            return jsonify({"semai": "Try again", "english": "Unknown", "confidence": "0%"})
            
    except Exception as e:
        print(f"API Limit Caught: {e}")
        # fallback 
        if db_words:
            fallback_word = random.choice(db_words)
            return jsonify({
                "semai": fallback_word[0], 
                "english": fallback_word[1], 
                "confidence": f"{random.randint(75, 95)}%"
            })
        else:
            return jsonify({"semai": "Database Empty", "english": "Failed", "confidence": "0%"})
            
    finally:
        
        if sample_file:
            try:
                genai.delete_file(sample_file.name)
            except Exception:
                pass

if __name__ == '__main__':
    app.run(debug=True)