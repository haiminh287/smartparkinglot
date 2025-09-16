import requests
import uuid
import hmac
import hashlib


def get_qr_momo(order_id, amount, redriectUrl, ipUrl):
    endpoint = "https://test-payment.momo.vn/v2/gateway/api/create"
    partnerCode = "MOMO"
    accessKey = "F8BBA842ECF85"
    secretKey = "K951B6PE1waDMi640xX08PD3vg6EkVlz"
    orderInfo = f"Mã đơn hàng: #{str(order_id)}"
    redirectUrl = f"http://localhost:3000{redriectUrl}"
    # ipnUrl = f"https://88918d3dc16c.ngrok-free.app{ipUrl}ip"
    ipnUrl = f"http://172.18.77.40:8000/api/cameras/{ipUrl}/"
    amount = str(int(amount))
    extraData = str(order_id)
    orderId = str(uuid.uuid4())
    requestId = str(uuid.uuid4())
    requestType = "captureWallet"
    print("orderId", orderId)
    print("amount", amount)
    # Tạo chữ ký (signature)
    rawSignature = (
        f"accessKey={accessKey}&amount={amount}&extraData={extraData}"
        f"&ipnUrl={ipnUrl}&orderId={orderId}&orderInfo={orderInfo}"
        f"&partnerCode={partnerCode}&redirectUrl={redirectUrl}"
        f"&requestId={requestId}&requestType={requestType}"
    )
    h = hmac.new(bytes(secretKey, 'utf-8'),
                 bytes(rawSignature, 'utf-8'), hashlib.sha256)
    signature = h.hexdigest()

    # Dữ liệu gửi đến API
    data = {
        'partnerCode': partnerCode,
        'partnerName': "Test",
        'storeId': "MomoTestStore",
        'requestId': requestId,
        'amount': amount,
        'orderId': orderId,
        'orderInfo': orderInfo,
        'redirectUrl': redirectUrl,
        'ipnUrl': ipnUrl,
        'lang': "vi",
        'extraData': extraData,
        'requestType': requestType,
        'signature': signature
    }

    response = requests.post(endpoint, json=data, headers={
                             'Content-Type': 'application/json'})
    print(f"Response status code: {response.status_code}")
    print(f"Response content: {response.json()}")
    return response


def ger_respone_momo(data):
    partnerCode = data.get('partnerCode')
    orderId = data.get('orderId')
    requestId = data.get('requestId')
    amount = data.get('amount')
    orderInfo = data.get('orderInfo')
    orderType = data.get('orderType')
    transId = data.get('transId')
    resultCode = data.get('resultCode')
    message = data.get('message')
    payType = data.get('payType')
    responseTime = data.get('responseTime')
    extraData = data.get('extraData')
    signature = data.get('signature')

    # Verify signature
    rawSignature = f"accessKey=F8BBA842ECF85&amount={amount}&extraData={extraData}&message={message}&orderId={orderId}&orderInfo={orderInfo}&orderType={orderType}&partnerCode={partnerCode}&payType={payType}&requestId={requestId}&responseTime={responseTime}&resultCode={resultCode}&transId={transId}"
    secretKey = "K951B6PE1waDMi640xX08PD3vg6EkVlz"
    h = hmac.new(bytes(secretKey, 'utf-8'),
                 bytes(rawSignature, 'utf-8'), hashlib.sha256)
    expected_signature = h.hexdigest()
    return resultCode
