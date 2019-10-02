import azure.cognitiveservices.speech as speechsdk
import configparser
import json
import pypapero
import sys
import time
import urllib.request as urllib_req
import urllib.parse as urllib_p

# シミュレーターID
simulator_id = "2crk9ymk"
robot_name = ""
ws_server_addr = ""

# 設定ファイルを読み込む
inifile = configparser.ConfigParser()
inifile.read('./property.ini', 'UTF-8')

'''
参考
https://github.com/Azure-Samples/cognitive-services-speech-sdk/blob/master/samples/python/console/speech_sample.py
'''
def speech_recognize_keyword_from_microphone():
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
    print('"{}" と呼びかけ、続けて何かおっしゃってください（英語は苦手）'.format(keyword))
    while not done:
        time.sleep(.5)

    return text.replace('アシスタント', '').replace('。', '')

def post_morphological_api(sentence):
    # 設定ファイルから読み込み
    morphological_api = inifile.get('morphological', 'morphological_api')
    service_url = inifile.get('morphological', 'service_url')

    # リクエスト作成
    headers = {"Content-Type" : "application/json"}
    obj = {"app_id": morphological_api,
        "request_id": "record001",
        "sentence": sentence,
        "info_filter": "form"
    }
    json_data = json.dumps(obj).encode("utf-8")
    request = urllib_req.Request(service_url, data=json_data, method="POST", headers=headers)

    # リクエスト送信、その後テキストを抽出、整形、返却
    with urllib_req.urlopen(request) as response:
        response_body = response.read().decode("utf-8")
        result_objs = json.loads(response_body.split('\n')[0])
        text = ""
        for item in result_objs["word_list"][0]:
            text += item[0] + " "
        return text

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
    headers = {"Authorization" : "Bearer " + client_access_token}
    request = urllib_req.Request(url, headers=headers)

    # リクエスト送信、その後JSON文字列を抽出、返却
    with urllib_req.urlopen(request) as response:
        json_str = response.read().decode('unicode-escape')
    return str(json_str)

def papero_operating_func(text):
    # Paperoオブジェクトを生成、指定されたテキストを発話し終了
    papero = pypapero.Papero(simulator_id, robot_name, ws_server_addr)
    papero.send_start_speech(text)
    print(text)
    sys.exit()

speech_to_text = speech_recognize_keyword_from_microphone()

if not speech_to_text:
    print("呼びかけ後すぐに発話してください")
    sys.exit()

text_to_morpheme = post_morphological_api(speech_to_text)
json_str = get_tag_from_wit(text_to_morpheme)

json_obj = json.loads(json_str)
print(json.dumps(json_obj, ensure_ascii=False, indent=2))

if 'recommend' in json_obj['entities']:
    if 'item' in json_obj['entities']:
        if 'what' in json_obj['entities']:
            text = "{}な{}はカレーパンだよ".format(
                json_obj['entities']['recommend'][0]['value'],
                json_obj['entities']['item'][0]['value'])
            papero_operating_func(text)

if 'popular' in json_obj['entities']:
    if 'item' in json_obj['entities']:
        if 'what' in json_obj['entities']:
            text = "{}な{}はアンパンだよ".format(
                json_obj['entities']['popular'][0]['value'],
                json_obj['entities']['item'][0]['value'])
            papero_operating_func(text)

if 'yourself' in json_obj['entities']:
    if 'name' in json_obj['entities']:
        if 'what' in json_obj['entities']:
            text = "ぼくの{}はパペロだよ".format(
                json_obj['entities']['name'][0]['value']
                )
            papero_operating_func(text)

if 'greeting' in json_obj['entities']:
            text = "{}".format(
                json_obj['entities']['greeting'][0]['value']
                )
            papero_operating_func(text)

if 'yoroshiku' in json_obj['entities']:
            text = "こちらこそよろしくお願いいたします"
            papero_operating_func(text)

if 'asks' in json_obj['entities']:
            text = "はい、なんですか？"
            papero_operating_func(text)

if 'first' in json_obj['entities']:
            text = "初めまして、お会いできてうれしいです"
            papero_operating_func(text)

text = "申し訳ございません、よくわかりませんでした。精進してまいります。"
papero_operating_func(text)
