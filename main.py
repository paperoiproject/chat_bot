import azure.cognitiveservices.speech as speechsdk
import configparser
from janome.tokenizer import Tokenizer
import json
import pypapero
import sys
import time
import urllib.request as urllib_req
import urllib.parse as urllib_p
from tuning import Tuning
import usb.core
import usb.util
import ssl
context = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
context.verify_mode = ssl.CERT_NONE

# シミュレータ / 実機 の指定
# 切り替え方
# """ シミュレータ or #""" シミュレータ

""" シミュレータ

   simulator_id = "7a2musbo"
   robot_name = ""
   ws_server_addr = ""

   """  # 実機

simulator_id = ""
robot_name = ""
ws_server_addr = "ws://192.168.1.1:8088/papero"
# """

# 設定ファイルを読み込む
inifile = configparser.ConfigParser()
inifile.read('./property.ini', 'UTF-8')


# 音声認識
def speech_recognize_keyword_from_microphone(mictuning):
    WAKE_WORD = "assistant"
    WAKE_WORD_MODEL = "./kws.table"

    # 設定ファイルから読み込み
    speech_key = inifile.get('speech_config', 'speech_key1')
    service_region = inifile.get('speech_config', 'service_region')
    language = inifile.get('speech_config', 'language')

    # speech config のインスタンス作成
    speech_config = speechsdk.SpeechConfig(
        subscription=speech_key,
        region=service_region,
        speech_recognition_language=language)

    # 指定された設定で speech recognizer を作成
    speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config)

    # Keyword Recognition Model のインスタンスを作成
    model = speechsdk.KeywordRecognitionModel(WAKE_WORD_MODEL)

    # Keyword Recognition Model がトリガーするフレーズ
    keyword = WAKE_WORD

    # キーワード認識継続を判定するトリガー
    done = False

    def stop_cb(evt):
        # イベント「evt」の受信時に連続認識を停止するコールバック
        speech_recognizer.stop_keyword_recognition()
        nonlocal done
        done = True

    def recognizing_cb(evt):
        # イベントを認識するためのコールバック
        if evt.result.reason == speechsdk.ResultReason.RecognizingKeyword:
            pass
        elif evt.result.reason == speechsdk.ResultReason.RecognizingSpeech:
            pass

    def recognized_cb(evt):
        # 認識されたイベントのコールバック
        if evt.result.reason == speechsdk.ResultReason.RecognizedKeyword:
            pass
        elif evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
            global text
            text = evt.result.text
            pass
        elif evt.result.reason == speechsdk.ResultReason.NoMatch:
            pass

    # コールバックを音声認識エンジンによって起動されたイベントに接続
    speech_recognizer.recognizing.connect(recognizing_cb)
    speech_recognizer.recognized.connect(recognized_cb)
    speech_recognizer.session_started.connect(lambda evt: print('', end=""))
    speech_recognizer.session_stopped.connect(lambda evt: print('', end=""))
    speech_recognizer.canceled.connect(lambda evt: print('', end=""))

    # セッションの停止またはキャンセルされたイベントで連続認識を停止
    speech_recognizer.session_stopped.connect(stop_cb)
    speech_recognizer.canceled.connect(stop_cb)

    # キーワード認識を開始
    speech_recognizer.start_keyword_recognition(model)
    print('"{}" と呼びかけ、続けて何かおっしゃってください'.format(keyword))
    while not done:
        dire = mictuning.direction
        time.sleep(.5)

    return text.replace('アシスタント', ''), dire


# 形態素解析
def post_morphological_janome(sentence):
    t = Tokenizer(wakati=True)

    text_to_morpheme = ""
    for token in t.tokenize(sentence):
        text_to_morpheme = text_to_morpheme + token + " "

    print("Janome↓")
    print(text_to_morpheme)
    print("\n")
    return text_to_morpheme


def get_tag_from_wit(text):
    # 設定ファイルから読み込み
    client_access_token = inifile.get('tag_from_wit', 'client_access_token')
    wit_api_host = inifile.get('tag_from_wit', 'wit_api_host')
    wit_api_version = inifile.get('tag_from_wit', 'wit_api_version')

    # クエリ文字列を作成、URLと合成
    query = urllib_p.urlencode({
        'v': wit_api_version,
        'q': text
    })
    url = wit_api_host + query

    # リクエスト作成
    headers = {"Authorization": "Bearer " + client_access_token}
    request = urllib_req.Request(url, headers=headers)

    # リクエスト送信、その後JSON文字列を抽出、返却
    with urllib_req.urlopen(request) as response:
        json_str = response.read().decode('unicode-escape')
    return str(json_str)


def papero_control_func(json_obj, dire):
    if 'yourself' in json_obj['entities']:
        text = "ぼくはパペロだよ。よろしくね。"
        json_post(text, dire)
        #papero_operating_func(text, dire)
        return

    if 'recommend' in json_obj['entities']:
        if 'item' in json_obj['entities']:
            if 'query' in json_obj['entities']:
                text = "オススメのパンはカレーパンだよ"
                json_post(text, dire)
                #papero_operating_func(text, dire)
                return

    if 'popular' in json_obj['entities']:
        if 'item' in json_obj['entities']:
            if 'query' in json_obj['entities']:
                text = "人気なパンはアンパンだよ"
                json_post(text, dire)
                #papero_operating_func(text, dire)
                return

    text = "申し訳ございません、よくわかりませんでした。"

    json_post(text, dire)
    #papero_operating_func(text, dire)


def papero_operating_func(text, dire):
    # Paperoオブジェクトを生成、指定されたテキストを発話し終了
    papero = pypapero.Papero(simulator_id, robot_name, ws_server_addr)
    if dire >= 180:
        dire = dire - 360
    if dire >= 80:
        dire = 80
    if dire <= -80:
        dire = -80
    print(f"方向は {dire} です")
    papero.send_move_head(["A20T500L", "R0T5000L", "A0T500L"], [
                          f"A{dire}T500L", "R0T5000L", "A0T500L"])
    papero.send_start_speech(text)
    print(text)


def json_post(text, dire):
    if dire >= 180:
        dire = dire - 360
    if dire >= 80:
        dire = 80
    if dire <= -80:
        dire = -80
    url = "https://10.70.84.77:443/chat/test"
    method = "POST"
    headers = {"Content-Type": "application/json"}

    # PythonオブジェクトをJSONに変換する
    obj = {"chat_text": text, "direction": str(dire)}
    json_data = json.dumps(obj).encode("utf-8")

    # httpリクエストを準備してPOST
    request = urllib_req.Request(
        url, data=json_data, method=method, headers=headers)
    with urllib_req.urlopen(request, context=context) as response:
        response_body = response.read().decode("utf-8")
        print(response_body)


try:
    # ReSpearker Mic Array v2.0に接続
    dev = usb.core.find(idVendor=0x2886, idProduct=0x0018)
    if dev:
        Mic_tuning = Tuning(dev)
        while True:
            time.sleep(1)

            speech_to_text, dire = speech_recognize_keyword_from_microphone(
                Mic_tuning)

            if not speech_to_text:
                print("呼びかけ後すぐに発話してください")
                sys.exit()

            print("認識しました。\n変換中...\n")

            text_to_morpheme = post_morphological_janome(speech_to_text)

            json_str = get_tag_from_wit(text_to_morpheme)

            json_obj = json.loads(json_str)

            papero_control_func(json_obj, dire)

    else:
        print("ReSpearker Mic Array v2.0が見つかりません。")
        sys.exit()

except KeyboardInterrupt:
    print("終了")
