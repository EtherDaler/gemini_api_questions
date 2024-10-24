from fastapi import FastAPI, File, UploadFile, HTTPException, Header, Depends
from pydantic import BaseModel
import PIL.Image
import google.generativeai as genai

app = FastAPI()


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
    gemini_key = read_config('GEMINI_KEY').strip()
    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel('gemini-pro')
    print("Gemini Key: ", gemini_key)
    keywords = {
        "ru": ["пасспорт", "заявление", "регистрация", "патент", "мигрант", "рвп", "внж", "гражданство", "миграционный"],
        "tj": ["паспор", "дархост", "сабт", "патент", "механик", "рвп", "внж", "гражданӣ", "мигратсионӣ"],
        "uz": ["паспорт", "ариза", "ройхатга олиш", "патент", "мигрант", "рвп", "внж", "гражданлик", "миграция"],
        "uz_latin": ["pasport", "ariza", "ro'yxatga olish", "patent", "migrant", "rvp", "vnj", "fuqarolik", "migratsiya"]
    }
    if request.lang not in keywords:
        raise HTTPException(status_code=400, detail="Unsupported language")
    if not any(keyword in request.question.lower() for keyword in keywords[request.lang]):
        raise HTTPException(status_code=400, detail=f"Question must contain one of the keywords: {', '.join(keywords[request.lang])}")
    if request.lang == 'tj':
        auxiliary_text = " То ҳадди имкон равшан ва ҳамаҷониба ҷавоб диҳед. Лутфан истинодҳои муфидро аз порталҳои давлатӣ пешниҳод кунед. Ҷавоби худро бо забони тоҷикӣ диҳед."
    elif request.lang == 'uz':
        auxiliary_text = " Iloji boricha aniq va to'liq javob bering. Iltimos, davlat portallaridan foydali havolalarni taqdim eting. Javobingizni tojik tilida bering."
    else:
        auxiliary_text = " Ответь максимально понятно и развернуто, и не забудь указать ссылки на полезные ресурсы."
    try:
        response = model.generate_content(request.question + auxiliary_text)
    except Exception as e:
        print(e)
        return HTTPException(status_code=400, detail="Error While request to gemini")

    # Пример ответа
    return {
        "message": "Question received successfully",
        "question": request.question,
        "lang": request.lang,
        "answer": response.text
    }


@app.post("/image_recognition")
async def read_image(image: UploadFile = File(...), api_key: str = Depends(verify_api_key)):
    gemini_key = read_config('GEMINI_KEY').strip()
    genai.configure(api_key=gemini_key)
    model_with_image = genai.GenerativeModel('gemini-1.5-flash')
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
        response = model_with_image.generate_content(["Прочитай и пришли данные с документа", image])
        if response and hasattr(response, 'text'):
            return {"data": response.text}
        else:
            return {"error": "No valid response text returned from the model."}
    except Exception as e:
        print(e)
        return HTTPException(status_code=400, detail="Failed response from gemini")
    return {"data": response.text}

