import PIL.Image
import requests
import base64
import google.generativeai as genai


from openai import OpenAI
from fastapi import FastAPI, File, UploadFile, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fake_useragent import UserAgent


ua = UserAgent()

app = FastAPI()


origins = [
    "*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def read_config(key: str):
    with open('key.txt', 'r') as file:
        for line in file:
            if key in line:
                start = line.find("=")
                return line[start+1:]
    return None


# Делаем зависимость для проверки API ключа
def verify_api_key(api_key: str = Header(...)):
    key = read_config("API_KEY").strip()
    if api_key != key:
        raise HTTPException(status_code=403, detail="Invalid API key")


class QuestionRequest(BaseModel):
    question: str
    lang: str


class ImageRequest(BaseModel):
    lang: str


@app.get("/")
async def home():
    return {"data": "Hello World"}


@app.post("/question")
async def submit_question(request: QuestionRequest, api_key: str = Depends(verify_api_key)):
    # Здесь вы можете добавить логику обработки запроса
    gpt_key = read_config('GPT_KEY').strip()
    client = OpenAI(api_key=gpt_key)
    gemini_key = read_config('GEMINI_KEY').strip()
    #genai.configure(api_key=gemini_key)
    #model = genai.GenerativeModel('gemini-1.0-pro')
    keywords = {
        "ru": ["пасспорт", "заявление", "регистрация", "патент", "мигрант", "рвп", "внж", "гражданство", "миграционный"],
        "tj": ["паспор", "дархост", "сабт", "бақайдгирӣ", "патент", "механик", "рвп", "внж", "гражданӣ", "мигратсионӣ"],
        "uz": ["паспорт", "ариза", "ройхатга олиш", "патент", "мигрант", "рвп", "внж", "гражданлик", "миграция", "pasport", "ariza", "ro'yxatga olish", "patent", "migrant", "rvp", "vnj", "fuqarolik", "migratsiya"]
    }
    k_ar = list()
    for lang in keywords.keys():
        k_ar += keywords[lang]
    print(k_ar)
    if request.lang not in keywords:
        raise HTTPException(status_code=400, detail="Unsupported language")
    if not any(keyword in request.question.lower() for keyword in k_ar):
        raise HTTPException(status_code=400, detail=f"Question must contain one of the keywords: {', '.join(keywords[request.lang])}")
    auxiliary_text = {
        'tj': " То ҳадди имкон равшан ва ҳамаҷониба ҷавоб диҳед. Лутфан истинодҳои муфидро аз порталҳои давлатӣ пешниҳод кунед. Ҷавоби худро бо забони тоҷикӣ диҳед.",
        'uz': " Iloji boricha aniq va to'liq javob bering. Iltimos, davlat portallaridan foydali havolalarni taqdim eting. Javobingizni tojik tilida bering.",
        'ru': " Ответь максимально понятно и развернуто, и не забудь указать ссылки на полезные ресурсы."
    }
    try:
        #response = model.generate_content(
        #    request.question + auxiliary_text.get(request.lang, "")
        #)
        response = client.chat.completions.create(
            model="gpt-4o",  # Использование модели GPT-4
            messages=[
                {"role": "system", "content": "Ты — эксперт в области документов и миграции."},
                {"role": "user", "content": request.question + auxiliary_text.get(request.lang, "")}
            ],
            max_tokens=200  # Максимальное количество токенов для ответа
        )
        answer = response.choices[0].message.content.strip()
    except Exception as e:
        print(e)
        # Теперь отправим запрос через requests с использованием HTTP/1.1
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={gemini_key}"  # URL Gemini API

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Content-Type": "application/json",  # Если тело запроса не в формате JSON
            "Accept": "*/*",
        }
        data = {"contents":[{"parts":[{"text":request.question}]}]}

        # Пример отправки POST-запроса с принудительным использованием HTTP/1.1
        try:
            response = requests.post(
                url,
                headers=headers,
                data=data,
                allow_redirects=True
            )
            response.raise_for_status()  # Проверка на ошибки HTTP
            answer = response.json()['text']
        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}")
            return HTTPException(status_code=500, detail="Error While request to gemini")

    # Пример ответа
    return {
        "message": "Question received successfully",
        "question": request.question + auxiliary_text.get(request.lang, ""),
        "lang": request.lang,
        "answer": answer
    }


def encode_image64(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


@app.post("/image_recognition")
async def read_image(image: UploadFile = File(...), api_key: str = Depends(verify_api_key)):
    gemini_key = read_config('GEMINI_KEY').strip()
    gpt_key = read_config('GPT_KEY').strip()
    client = OpenAI(api_key=gpt_key)
    #genai.configure(api_key=gemini_key)
    #model_with_image = genai.GenerativeModel('gemini-1.5-flash')
    try:
        contents = await image.read()
        with open(f"uploads/{image.filename}", "wb") as f:
            f.write(contents)
    except Exception as e:
        print(e)
        return HTTPException(status_code=500, detail="Failed to save image")

    try:
        photo = f"uploads/{image.filename}"
        image = PIL.Image.open(photo)
        base64_image = encode_image64(photo)
        #response = model_with_image.generate_content(["Прочитай и пришли данные с документа", image])
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Ты помощник, который считывает текст с изображений и возвращает его."},
                {"role": "user", "content": [
                    {"type": "text", "text": "Выведи пасспортные данные с изображения."},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}
                    }
                ]}
            ],
            temperature = 0.0
        )
        return {"data": response.choices[0].message.content}
    except Exception as e:
        print(e)
        return HTTPException(status_code=400, detail="Failed response from gemini")

