from flask import Flask, render_template, request, redirect, session
import random
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Настройки для авторизации в Google Sheets API
SCOPE = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
CREDENTIALS_FILE = 'online-questions-460117-8c2f824b82db.json'  # файл ключей от аккаунта сервиса Google
SHEET_NAME = 'Результаты тестируемых'

app = Flask(__name__)
app.secret_key = 'a7d5b4c6e9f2a3bc'


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/generate_test', methods=['POST'])
def generate_test():
    first_name = request.form['firstName']
    last_name = request.form['lastName']

    questions = {
        'choice': load_questions('choice'),
        'matching': load_questions('matching'),
        'open': load_questions('open')
    }

    selected_questions = select_random_questions(questions)

    session['test'] = {
        'first_name': first_name,
        'last_name': last_name,
        'selected_questions': selected_questions
    }

    return redirect('/test')


@app.route('/test')
def show_test():
    if 'test' not in session:
        return redirect('/')

    test_data = session.get('test')
    selected_questions = test_data['selected_questions']

    for question_type in selected_questions.keys():
        shuffle_answers(selected_questions[question_type])

    return render_template('test.html', data=test_data)


@app.route('/submit_test', methods=['POST'])
def submit_test():
    user_answers = {}
    correct_count = 0
    total_questions = 0

    test_data = session.pop('test', None)
    if not test_data:
        return redirect('/')

    for qtype, questions in test_data['selected_questions'].items():
        for i, question in enumerate(questions):
            key = f"{qtype}_{i}"
            answer = request.form[key]

            if check_answer(qtype, question, answer):
                correct_count += 1

            user_answers[f'{qtype}_Q{i + 1}'] = answer

        total_questions += len(questions)

    record_results(test_data['first_name'], test_data['last_name'], correct_count, total_questions, user_answers)

    return f"Тест успешно отправлен! Верных ответов {correct_count}/{total_questions}. Результаты сохранены."


def load_questions(question_type):
    with open(f'data/{question_type}_questions.json') as file:
        return json.load(file)


def select_random_questions(questions_dict):
    selected_questions = {}
    for qtype, questions in questions_dict.items():
        num_to_select = min(len(questions), 5)
        selected_questions[qtype] = random.sample(questions, k=num_to_select)
    return selected_questions


def shuffle_answers(questions_list):
    for question in questions_list:
        random.shuffle(question['answers'])


def check_answer(question_type, question, user_answer):
    correct_answer = question['answer']
    if question_type == 'choice':
        return user_answer == str(correct_answer)
    elif question_type == 'matching':
        matching_pairs = dict(zip(user_answer.split(','), map(int, correct_answer)))
        return all(matching_pairs[k] == v for k, v in
                   zip(matching_pairs.keys(), sorted(map(str, range(1, len(matching_pairs) + 1)))))
    else:
        return False  # Для открытых вопросов пока упрощенно считаем неверными


def record_results(first_name, last_name, correct_count, total_questions, answers):
    credentials = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, SCOPE)
    client = gspread.authorize(credentials)
    sheet = client.open(SHEET_NAME).sheet1

    row = [
        first_name + ' ' + last_name,
        f'{correct_count}/{total_questions}',
        *(f'{k}: {v}' for k, v in answers.items())
    ]
    sheet.append_row(row)


if __name__ == '__main__':
    app.run(debug=True)