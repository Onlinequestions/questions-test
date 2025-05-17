from flask import Flask, render_template, request, redirect, session
import random
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Настройка приложения
app = Flask(__name__)
app.secret_key = 'zjWvyV_bL1UfqA0G_XJqRwfB8P2uYsNhOiqDfvYZGn4='  # Замените на реальный ключ

# Настройки для авторизации в Google Sheets API
SCOPE = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
CREDENTIALS_FILE = 'online-questions-460117-8c2f824b82db.json'  # Путь к файлу с ключами
SHEET_NAME = 'Результаты тестируемых'  # Название листа в Google Sheets


@app.route('/', methods=['GET'])
def home():
    """Отображение начальной страницы."""
    return render_template('index.html')


@app.route('/generate_test', methods=['POST'])
def generate_test():
    """
    Генерирует вариант теста на основании введённых данных.
    """
    first_name = request.form['firstName']
    last_name = request.form['lastName']

    # Загрузка вопросов из разных категорий
    questions = {
        'choice': load_questions('choice'),
        'matching': load_questions('matching'),
        'open': load_questions('open')
    }

    # Выбор случайных вопросов из каждой категории
    selected_questions = select_random_questions(questions)

    # Сохранение данных о тесте в сессии
    session['test'] = {
        'first_name': first_name,
        'last_name': last_name,
        'selected_questions': selected_questions
    }

    return redirect('/test')


@app.route('/test', methods=['GET'])
def show_test():
    """
    Отображает сам тест с выбранными вопросами.
    """
    if 'test' not in session:
        return redirect('/')

    test_data = session.get('test')
    selected_questions = test_data['selected_questions']

    # Перемешиваем варианты ответов для вопросов с выбором
    for question_type in selected_questions.keys():
        shuffle_answers(selected_questions[question_type])

    return render_template('test.html', data=test_data)


@app.route('/submit_test', methods=['POST'])
def submit_test():
    """
    Отправляет результаты теста в Google Sheets и выводит итоговую оценку.
    """
    if 'test' not in session:
        return redirect('/')

    test_data = session.pop('test', None)
    if not test_data:
        return redirect('/')

    user_answers = {}  # Ответы пользователя
    correct_count = 0  # Количество правильных ответов
    total_questions = 0  # Всего вопросов

    # Проходим по каждому типу вопросов и проверяем ответы
    for qtype, questions in test_data['selected_questions'].items():
        for i, question in enumerate(questions):
            key = f"{qtype}_{i}"
            answer = request.form[key]

            is_correct = check_answer(qtype, question, answer)
            if is_correct:
                correct_count += 1

            user_answers[f'{qtype}_Q{i + 1}'] = answer

        total_questions += len(questions)

    # Запись результата в Google Sheets
    record_results(test_data['first_name'], test_data['last_name'], correct_count, total_questions, user_answers)

    return f"""
    Тест успешно отправлен!<br />
    Верных ответов: {correct_count}/{total_questions}<br />
    Ваши результаты были сохранены в Google Sheets.<br /><br />
    Спасибо за участие!
    """


def load_questions(question_type):
    """
    Загружаем вопросы из соответствующих JSON-файлов.
    """
    with open(f'data/{question_type}_questions.json') as file:
        return json.load(file)


def select_random_questions(questions_dict):
    """
    Случайно выбираем по 5 вопросов из каждой категории.
    """
    selected_questions = {}
    for qtype, questions in questions_dict.items():
        num_to_select = min(len(questions), 5)
        selected_questions[qtype] = random.sample(questions, k=num_to_select)
    return selected_questions


def shuffle_answers(questions_list):
    """
    Перемешивает порядок ответов для вопросов с выбором.
    """
    for question in questions_list:
        random.shuffle(question['answers'])


def check_answer(question_type, question, user_answer):
    """
    Проверяет правильность ответа.
    """
    correct_answer = question['answer']
    if question_type == 'choice':
        return user_answer == str(correct_answer)
    elif question_type == 'matching':
        pairs = dict(zip(user_answer.split(','), map(int, correct_answer)))
        return all(pairs[k] == v for k, v in zip(sorted(pairs.keys()), sorted(map(str, range(1, len(pairs) + 1)))))
    else:
        return False  # Открытые вопросы считаем неверными


def record_results(first_name, last_name, correct_count, total_questions, answers):
    """
    Записываем результаты в Google Sheets.
    """
    credentials = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, SCOPE)
    client = gspread.authorize(credentials)
    sheet = client.open(SHEET_NAME).sheet1

    # Данные для записи в таблицу
    row = [
              first_name + ' ' + last_name,
              f'{correct_count}/{total_questions}'
          ] + list(answers.values())

    sheet.append_row(row)


if __name__ == '__main__':
    app.run(debug=True)