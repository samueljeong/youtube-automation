"""
AI Tools API Blueprint
/api/ai-tools/* 엔드포인트 담당

기능:
- YouTube 리서처 (검색, 자막, 댓글)
- 트렌드 스캐너 (뉴스, 검색어)
- 이미지 생성 (Gemini Imagen)
- 이미지 분석 (Gemini Vision)
- 도구 결과 채팅
"""

import os
from flask import Blueprint, request, jsonify, render_template

# Blueprint 생성
ai_tools_bp = Blueprint('ai_tools', __name__)


@ai_tools_bp.route('/ai-tools')
def ai_tools_page():
    """AI Tools 페이지 렌더링"""
    return render_template('ai-tools.html')


@ai_tools_bp.route('/api/ai-tools/youtube', methods=['POST'])
def api_ai_tools_youtube():
    """YouTube 리서처: 검색, 자막 추출, 댓글 분석"""
    try:
        import re
        import requests as req

        data = request.get_json()
        query = data.get('query', '').strip()
        action = data.get('action', 'search')
        limit = data.get('limit', 10)

        if not query:
            return jsonify({"ok": False, "error": "검색어를 입력하세요"})

        # YouTube URL에서 video ID 추출
        video_id = None
        if 'youtube.com/watch' in query or 'youtu.be/' in query:
            match = re.search(r'(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})', query)
            if match:
                video_id = match.group(1)

        result = {"ok": True}

        if action == 'search':
            api_key = os.environ.get('YOUTUBE_API_KEY') or os.environ.get('YOUTUBE_API_KEY_2')
            if not api_key:
                return jsonify({"ok": False, "error": "YouTube API 키가 설정되지 않았습니다"})

            search_url = "https://www.googleapis.com/youtube/v3/search"
            params = {
                'part': 'snippet',
                'q': query,
                'type': 'video',
                'maxResults': min(limit, 50),
                'key': api_key,
                'regionCode': 'KR',
                'relevanceLanguage': 'ko'
            }

            resp = req.get(search_url, params=params, timeout=30)
            if resp.status_code != 200:
                return jsonify({"ok": False, "error": f"YouTube API 오류: {resp.status_code}"})

            search_data = resp.json()
            videos = []

            for item in search_data.get('items', []):
                snippet = item.get('snippet', {})
                videos.append({
                    'id': item.get('id', {}).get('videoId'),
                    'title': snippet.get('title', ''),
                    'channel': snippet.get('channelTitle', ''),
                    'thumbnail': snippet.get('thumbnails', {}).get('medium', {}).get('url', ''),
                    'published': snippet.get('publishedAt', ''),
                    'description': snippet.get('description', '')[:200]
                })

            result['videos'] = videos

        elif action == 'transcript':
            target_id = video_id or query
            try:
                from youtube_transcript_api import YouTubeTranscriptApi

                transcript_list = YouTubeTranscriptApi.list_transcripts(target_id)
                transcript = None

                try:
                    transcript = transcript_list.find_transcript(['ko'])
                except:
                    try:
                        transcript = transcript_list.find_transcript(['en'])
                    except:
                        try:
                            transcript = transcript_list.find_generated_transcript(['ko', 'en'])
                        except:
                            pass

                if transcript:
                    captions = transcript.fetch()
                    full_text = ' '.join([c['text'] for c in captions])
                    result['transcript'] = full_text
                    result['video_id'] = target_id
                else:
                    result['transcript'] = '자막을 찾을 수 없습니다.'

            except Exception as e:
                result['transcript'] = f'자막 추출 실패: {str(e)}'

        elif action == 'comments':
            target_id = video_id or query
            api_key = os.environ.get('YOUTUBE_API_KEY') or os.environ.get('YOUTUBE_API_KEY_2')
            if not api_key:
                return jsonify({"ok": False, "error": "YouTube API 키가 설정되지 않았습니다"})

            comments_url = "https://www.googleapis.com/youtube/v3/commentThreads"
            params = {
                'part': 'snippet',
                'videoId': target_id,
                'maxResults': min(limit, 100),
                'order': 'relevance',
                'key': api_key
            }

            resp = req.get(comments_url, params=params, timeout=30)
            if resp.status_code != 200:
                return jsonify({"ok": False, "error": f"댓글 API 오류: {resp.status_code}"})

            comments_data = resp.json()
            comments = []

            for item in comments_data.get('items', []):
                snippet = item.get('snippet', {}).get('topLevelComment', {}).get('snippet', {})
                comments.append({
                    'author': snippet.get('authorDisplayName', ''),
                    'text': snippet.get('textDisplay', ''),
                    'likes': snippet.get('likeCount', 0),
                    'published': snippet.get('publishedAt', '')
                })

            result['comments'] = comments
            result['video_id'] = target_id

        elif action == 'channel':
            result['channel_info'] = {'message': '채널 분석 기능은 준비 중입니다.'}

        return jsonify(result)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)})


@ai_tools_bp.route('/api/ai-tools/trend', methods=['POST'])
def api_ai_tools_trend():
    """트렌드 스캐너: 뉴스, 검색어 트렌드"""
    try:
        import requests
        import feedparser
        from collections import Counter

        data = request.get_json()
        source = data.get('source', 'news')
        category = data.get('category', 'all')
        keyword = data.get('keyword', '')

        result = {"ok": True}

        if source == 'news':
            category_queries = {
                'all': '뉴스',
                'economy': '경제 금융 주식',
                'tech': '기술 AI 반도체',
                'entertainment': '연예 드라마 영화',
                'sports': '스포츠 축구 야구'
            }

            search_query = keyword if keyword else category_queries.get(category, '뉴스')
            encoded_query = requests.utils.quote(search_query)
            rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"

            feed = feedparser.parse(rss_url)

            news = []
            for entry in feed.entries[:20]:
                source_name = ''
                if ' - ' in entry.title:
                    parts = entry.title.rsplit(' - ', 1)
                    title = parts[0]
                    source_name = parts[1] if len(parts) > 1 else ''
                else:
                    title = entry.title

                news.append({
                    'title': title,
                    'source': source_name,
                    'link': entry.link,
                    'time': entry.get('published', ''),
                    'summary': entry.get('summary', '')[:200] if entry.get('summary') else ''
                })

            result['news'] = news

        elif source == 'search':
            trends = []
            rss_url = "https://news.google.com/rss?hl=ko&gl=KR&ceid=KR:ko"
            feed = feedparser.parse(rss_url)

            words = Counter()

            for entry in feed.entries[:30]:
                title = entry.title.split(' - ')[0]
                for word in title.split():
                    if len(word) >= 2 and not word.isdigit():
                        words[word] += 1

            for word, count in words.most_common(20):
                trends.append({
                    'keyword': word,
                    'volume': f'{count}건'
                })

            result['trends'] = trends

        elif source == 'social':
            result['social'] = {'message': '소셜 미디어 트렌드는 준비 중입니다.'}

        return jsonify(result)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)})


@ai_tools_bp.route('/api/ai-tools/image-generate', methods=['POST'])
def api_ai_tools_image_generate():
    """이미지 생성기: Gemini Imagen"""
    try:
        import base64
        import uuid

        data = request.get_json()
        prompt = data.get('prompt', '').strip()
        style = data.get('style', 'realistic')
        ratio = data.get('ratio', '16:9')

        if not prompt:
            return jsonify({"ok": False, "error": "이미지 설명을 입력하세요"})

        style_prompts = {
            'realistic': 'photorealistic, high detail, professional photography',
            'webtoon': 'Korean webtoon style, manhwa art style, clean lines, vibrant colors',
            'cinematic': 'cinematic lighting, movie scene, dramatic atmosphere, 4K',
            'illustration': 'digital illustration, artistic, colorful, detailed artwork',
            '3d': '3D render, Unreal Engine, octane render, high quality CGI'
        }

        style_suffix = style_prompts.get(style, '')
        full_prompt = f"{prompt}, {style_suffix}"

        ratio_map = {
            '16:9': (1280, 720),
            '9:16': (720, 1280),
            '1:1': (1024, 1024),
            '4:3': (1024, 768)
        }
        width, height = ratio_map.get(ratio, (1280, 720))

        from image import generate_image_base64, GEMINI_FLASH

        image_data = generate_image_base64(
            prompt=full_prompt,
            width=width,
            height=height,
            model=GEMINI_FLASH
        )

        if image_data:
            filename = f"generated_{uuid.uuid4().hex[:8]}.png"
            filepath = os.path.join("static", "generated", filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            with open(filepath, 'wb') as f:
                f.write(base64.b64decode(image_data))

            image_url = f"/static/generated/{filename}"

            return jsonify({
                "ok": True,
                "image_url": image_url,
                "prompt_used": full_prompt
            })
        else:
            return jsonify({"ok": False, "error": "이미지 생성에 실패했습니다"})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)})


@ai_tools_bp.route('/api/ai-tools/vision', methods=['POST'])
def api_ai_tools_vision():
    """이미지 분석기: Gemini Vision"""
    try:
        import base64
        import requests as req

        if request.content_type and 'multipart/form-data' in request.content_type:
            file = request.files.get('file')
            prompt = request.form.get('prompt', '이 이미지를 자세히 분석해주세요.')

            if not file:
                return jsonify({"ok": False, "error": "파일을 업로드하세요"})

            image_data = base64.b64encode(file.read()).decode('utf-8')
            image_url = f"data:{file.content_type};base64,{image_data}"

        else:
            data = request.get_json()
            url = data.get('url', '').strip()
            prompt = data.get('prompt', '이 이미지를 자세히 분석해주세요.')

            if not url:
                return jsonify({"ok": False, "error": "이미지 URL을 입력하세요"})

            image_url = url

        import google.generativeai as genai

        api_key = os.environ.get('GOOGLE_API_KEY')
        if not api_key:
            return jsonify({"ok": False, "error": "Google API 키가 설정되지 않았습니다"})

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')

        if image_url.startswith('data:'):
            header, data = image_url.split(',', 1)
            mime_type = header.split(';')[0].split(':')[1]
            image_bytes = base64.b64decode(data)

            image_part = {
                'mime_type': mime_type,
                'data': image_bytes
            }
        else:
            resp = req.get(image_url, timeout=30)
            if resp.status_code != 200:
                return jsonify({"ok": False, "error": "이미지를 다운로드할 수 없습니다"})

            content_type = resp.headers.get('content-type', 'image/jpeg')
            image_part = {
                'mime_type': content_type.split(';')[0],
                'data': resp.content
            }

        response = model.generate_content([prompt, image_part])
        analysis = response.text if response.text else "분석 결과를 가져올 수 없습니다."

        return jsonify({
            "ok": True,
            "analysis": analysis,
            "image_url": image_url if not image_url.startswith('data:') else None
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)})


@ai_tools_bp.route('/api/ai-tools/chat', methods=['POST'])
def api_ai_tools_chat():
    """도구 결과에 대한 추가 대화"""
    try:
        from openai import OpenAI

        data = request.get_json()
        message = data.get('message', '')
        context = data.get('context', '')
        history = data.get('history', [])

        if not message:
            return jsonify({"ok": False, "error": "메시지를 입력하세요"})

        client = OpenAI()

        messages = [
            {
                "role": "system",
                "content": """당신은 AI 도구 결과를 분석하고 활용하는 것을 돕는 어시스턴트입니다.
사용자가 도구(YouTube 검색, 트렌드 분석, 이미지 생성 등)의 결과물에 대해 질문하면,
해당 컨텍스트를 바탕으로 유용한 인사이트, 요약, 아이디어를 제공하세요.

응답은 간결하고 실용적으로 작성하세요. 한국어로 답변하세요."""
            }
        ]

        for h in history[-6:]:
            messages.append({
                "role": h.get('role', 'user'),
                "content": h.get('content', '')
            })

        user_content = message
        if context:
            user_content = f"[도구 결과 컨텍스트]\n{context[:2000]}\n\n[사용자 질문]\n{message}"

        messages.append({"role": "user", "content": user_content})

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.7,
            max_tokens=1000
        )

        assistant_response = response.choices[0].message.content

        return jsonify({
            "ok": True,
            "response": assistant_response
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)})
