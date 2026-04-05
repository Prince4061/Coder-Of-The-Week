from flask import Flask, render_template, request, jsonify, send_file
import csv
import json
import os
from dotenv import load_dotenv
load_dotenv(override=True)
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate

app = Flask(__name__)
DB_FILE = 'scores.csv'
QUESTIONS_FILE = 'questions.json'

# Initialize questions.json with default template if not exists
def init_questions():
    if not os.path.exists(QUESTIONS_FILE):
        default_qs = [
            {
                "id": "1", 
                "text": "What is the capital of India?", 
                "options": {"a": "Mumbai", "b": "New Delhi", "c": "Kolkata", "d": "Chennai"}, 
                "answer": "b"
            },
            {
                "id": "2", 
                "text": "Which programming language is used for Flask?", 
                "options": {"a": "Java", "b": "Python", "c": "C++", "d": "Ruby"}, 
                "answer": "b"
            },
            {
                "id": "3", 
                "text": "Who is known as the father of computers?", 
                "options": {"a": "Charles Babbage", "b": "Alan Turing", "c": "Bill Gates", "d": "Steve Jobs"}, 
                "answer": "a"
            }
        ]
        with open(QUESTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_qs, f, indent=4)

def load_questions():
    init_questions()
    try:
        with open(QUESTIONS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []

# Initialize scores DB
if not os.path.exists(DB_FILE):
    with open(DB_FILE, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['ID', 'Name', 'Score'])

def read_db():
    users = []
    if os.path.exists(DB_FILE):
        with open(DB_FILE, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    row['Score'] = int(row['Score']) # ensure score is integer
                    users.append(row)
                except ValueError:
                    pass
    return users

def write_db(users):
    with open(DB_FILE, mode='w', newline='', encoding='utf-8') as f:
        fieldnames = ['ID', 'Name', 'Score']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(users)


# ==== FRONT PAGES ==== #

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/test')
def test_page():
    return render_template('test.html')

@app.route('/leaderboard')
def leaderboard_page():
    return render_template('leaderboard.html')

@app.route('/admin')
def admin_page():
    return render_template('admin.html')


# ==== ADMIN APIS ==== #

@app.route('/api/upload-questions', methods=['POST'])
def upload_questions():
    if 'file' not in request.files:
        print("Upload Error: No file part in request.files")
        return jsonify({"success": False, "message": "No file part"}), 400
    
    file = request.files['file']
    print(f"Received file upload attempt: {file.filename}")
    
    if file.filename == '':
        print("Upload Error: No selected file")
        return jsonify({"success": False, "message": "No selected file"}), 400
    
    if file and file.filename.endswith('.json'):
        try:
            content = file.read().decode('utf-8-sig')
            print(f"Extracted content length: {len(content)}")
            
            js_data = json.loads(content)
            
            if not isinstance(js_data, list):
                print("Upload Error: Parsed JSON is not a list")
                return jsonify({"success": False, "message": "JSON structure must start with a [ list ]"}), 400
                
            # Overwrite the existing questions.json file securely
            with open(QUESTIONS_FILE, 'w', encoding='utf-8') as f:
                json.dump(js_data, f, indent=4)
                
            print("Upload Success!")
            return jsonify({"success": True, "message": "Questions updated successfully!"})
        except BaseException as e:
            print(f"Upload Exception: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({"success": False, "message": f"Syntax Error in JSON file: {str(e)}"}), 400
            
    print("Upload Error: Filename does not end with .json")
    return jsonify({"success": False, "message": "Only .json files are allowed!"}), 400

@app.route('/api/download-template', methods=['GET'])
def download_template():
    init_questions() # Make sure it exists
    
    from flask import make_response
    with open(QUESTIONS_FILE, 'r', encoding='utf-8') as f:
        data = f.read()
        
    response = make_response(data)
    response.headers['Content-Type'] = 'application/json'
    response.headers['Content-Disposition'] = 'attachment; filename=questions_template.json'
    return response


# ==== TEST APIS ==== #

@app.route('/api/questions', methods=['GET'])
def get_questions():
    # Send questions dynamically loaded from JSON without the answers
    test_q = []
    all_qs = load_questions()
    for q in all_qs:
        test_q.append({
            "id": q.get("id"),
            "text": q.get("text"),
            "options": q.get("options", {})
        })
    return jsonify(test_q)

@app.route('/api/submit-test', methods=['POST'])
def submit_test():
    data = request.json
    name = data.get('name', 'Anonymous')
    answers = data.get('answers', {})
    
    all_qs = load_questions()
    score = 0
    analysis_data = []
    
    for q in all_qs:
        ans_key = answers.get(str(q['id']))
        correct_key = q.get('answer', '')
        
        user_answered = q.get('options', {}).get(ans_key, 'Skipped')
        correct_answer = q.get('options', {}).get(correct_key, 'Unknown')
        
        is_correct = (ans_key and ans_key.lower() == str(correct_key).lower())
        if is_correct:
            score += 1
            
        analysis_data.append(f"Q: {q['text']} | Student: {user_answered} | Correct: {correct_answer} | Is Correct: {is_correct}")
            
    users = read_db()
    new_id = str(len(users) + 1)
    users.append({
        'ID': new_id,
        'Name': name,
        'Score': score
    })
    write_db(users)
    
    # LangChain Integration
    ai_feedback = "AI Feedback..."
    try:
        llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0.7)
        prompt = PromptTemplate.from_template(
            "You are an encouraging AI tutor playing the role of an Indian teacher.\n"
            "Student Name: {name}\n"
            "Score: {score}/{total}\n"
            "Test Details:\n{test_data}\n\n"
            "Analyze the student's performance and provide feedback STRICTLY in 'Hinglish' (Hindi language written using English alphabet, e.g. 'Tumne acha perform kiya hai').\n"
            "Return the output STRICTLY as a JSON object with the following keys. The values for all these keys MUST be in Hinglish:\n"
            "- \"strength\": 1-2 sentence about their strong areas in Hinglish.\n"
            "- \"weakness\": 1-2 sentence about their weak areas in Hinglish.\n"
            "- \"suggestion\": Actionable advice in Hinglish on how they can improve.\n"
            "Do NOT include any markdown formatting like ```json, just return the raw JSON object."
        )
        chain = prompt | llm
        response = chain.invoke({
            "name": name,
            "test_data": "\n".join(analysis_data),
            "score": score,
            "total": len(all_qs)
        })
        
        content = response.content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
            
        import json
        ai_data = json.loads(content.strip())
        
        ai_feedback = f"""
            <div style='margin-bottom: 0.8rem;'><strong style='color:#34d399;'>💪 Strength:</strong> {ai_data.get('strength', 'N/A')}</div>
            <div style='margin-bottom: 0.8rem;'><strong style='color:#f87171;'>⚠️ Weakness:</strong> {ai_data.get('weakness', 'N/A')}</div>
            <div><strong style='color:#fbbf24;'>💡 Suggestion:</strong> {ai_data.get('suggestion', 'N/A')}</div>
        """
    except Exception as e:
        print(f"LLM Error: {e}")
        ai_feedback = "Tumhara score bohot accha hai! Keep practicing!"
    
    return jsonify({"success": True, "score": score, "total": len(all_qs), "feedback": ai_feedback, "message": "Test submitted successfully!"})

@app.route('/api/leaderboard', methods=['GET'])
def get_leaderboard():
    users = read_db()
    # Sort users by Score in descending order
    users.sort(key=lambda x: int(x.get('Score', 0)), reverse=True)
    return jsonify(users)

if __name__ == '__main__':
    app.run(debug=True)
