"""通过网页登录方式获取 iNaturalist API Token"""
import sys, re, requests
sys.path.insert(0, '.')
from config import INATURALIST_USERNAME, INATURALIST_PASSWORD

session = requests.Session()
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'

# Step1: 获取登录页拿 CSRF token
r = session.get('https://www.inaturalist.org/users/sign_in',
                timeout=12, headers={'User-Agent': UA})
print('登录页:', r.status_code)

csrf = re.search(r'name="authenticity_token" value="([^"]+)"', r.text)
if not csrf:
    print('未找到 CSRF token，页面片段:', r.text[:300])
    sys.exit(1)

# Step2: 提交登录
r2 = session.post(
    'https://www.inaturalist.org/users/sign_in',
    data={
        'user[login]': INATURALIST_USERNAME,
        'user[password]': INATURALIST_PASSWORD,
        'authenticity_token': csrf.group(1),
    },
    headers={'User-Agent': UA, 'Referer': 'https://www.inaturalist.org/users/sign_in'},
    allow_redirects=True, timeout=12,
)
print('登录结果:', r2.status_code, r2.url)

# Step3: 拿 API Token
r3 = session.get(
    'https://www.inaturalist.org/users/api_token',
    headers={'User-Agent': UA, 'Accept': 'application/json'},
    timeout=12,
)
print('API token 接口:', r3.status_code)
data = r3.json()
api_token = data.get('api_token', '')
if api_token:
    print('Token 获取成功:', api_token[:40], '...')
else:
    print('失败:', data)
