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
CREDENTIALS_FILE = 'data/single-cab-460119-a7-38f35d183f6f.json'  # Новый путь к файлу с ключами
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

    # Перемешивание вариантов ответов для вопросов с выбором
    for question_type in selected_questions.keys():
        shuffle_answers(selected_questions[question_type])

    return render_template('test.html', data=test_data)


@app.route('/submit_test', methods=['POST'])
def submit_test():
    if 'test' not in session:
        return redirect('/')

    test_data = session.pop('test', None)
    if not test_data:
        return redirect('/')

    user_answers = {}  # Ответы пользователя
    correct_count = 0  # Количество правильных ответов
    total_questions = 0  # Всего вопросов

    # Проверка правильности ответов
    for qtype, questions in test_data['selected_questions'].items():
        for i, question in enumerate(questions):
            key = f"{qtype}_{i}"
            answer = request.form.get(key)

            if answer is not None:
                if check_answer(qtype, question, answer):
                    correct_count += 1

                user_answers.setdefault(qtype, {})[key] = answer
            else:
                print(f"Warning: Question '{key}' did not have an answer submitted.")

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
    # Чтение файла с явным указанием кодировки UTF-8
    with open(f'data/{question_type}_questions.json', encoding='utf-8') as file:
        return json.load(file)


def select_random_questions(questions_dict):
    selected_questions = {}
    for qtype, questions in questions_dict.items():
        # Убеждаемся, что questions — это список
        if isinstance(questions, list):
            num_to_select = min(len(questions), 5)
            selected_questions[qtype] = random.sample(questions, k=num_to_select)
        else:
            print(f"Произошла ошибка: '{qtype}' не является списком")
    return selected_questions


def shuffle_answers(questions_list):
    for question in questions_list:
        if 'answers' in question:
            random.shuffle(question['answers'])
        else:
            continue  # Пропускаем вопросы без поля 'answers'


def check_answer(question_type, question, user_answer):
    """
    Проверяет правильность ответа.
    """
    if 'answer' in question:
        correct_answer = question['answer']
        if question_type == 'choice':
            return user_answer == str(correct_answer)
        elif question_type == 'matching':
            # Логика для сопоставляющих вопросов
            pass
    return False  # Возвращаем False, если поле 'answer' отсутствует


def record_results(first_name, last_name, correct_count, total_questions, user_answers):
    """
    Записывает результаты в Google Sheets.
    """
    credentials = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, SCOPE)
    client = gspread.authorize(credentials)
    sheet = client.open(SHEET_NAME).sheet1

    # Готовим строку для записи
    row = [
        first_name + ' ' + last_name,
        f'{correct_count}/{total_questions}'
    ]

    # Записываем ответы на вопросы
    for qtype, answers in user_answers.items():
        for key, value in answers.items():
            row.extend([key, value])

    sheet.append_row(row)


if __name__ == '__main__':
    app.run(debug=True)