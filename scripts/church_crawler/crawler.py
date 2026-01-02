#!/usr/bin/env python3
"""
교적 크롤링 + church-registry 업로드 스크립트

기능:
1. god4u.dimode.co.kr에서 교적 데이터 크롤링
2. 프로필 사진 다운로드
3. church-registry.onrender.com에 업로드

사용법:
1. 브라우저에서 god4u.dimode.co.kr 로그인
2. F12 → Application → Cookies에서 쿠키 값 복사
3. 아래 COOKIES 딕셔너리에 붙여넣기
4. python crawler.py 실행
"""

import requests
import json
import csv
import time
import base64
import os
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============================================================
# 설정
# ============================================================
COOKIES = {
    "ASP.NET_SessionId": "xgsyv0zp5q0b14znzorohsk2",
    "pastorinfo": "sUser=%c1%a4%bb%e7%b9%ab%bf%a4&sID=5700&sUserName=%c1%a4%bb%e7%b9%ab%bf%a4&sIsAdmin=1&churchid=god4u&chname=%c0%c7%c1%a4%ba%ce%c1%df%be%d3%b1%b3%c8%b8&sChurchAuth=OK&sCashAuth=OK&sSCashAuth=&sRangeAuth=OK&sSchoolAuth=OK&sYouthAuth=OK",
    "AUTOLOGIN": "YES",
}

# god4u API 설정
GOD4U_BASE_URL = "http://god4u.dimode.co.kr"
GOD4U_API_URL = f"{GOD4U_BASE_URL}/Handler/GetPersonListMobileJSon.asmx/GetPersonSearchListDefault"
GOD4U_PHOTO_URL = f"{GOD4U_BASE_URL}/Handler/DisplayImage.ashx"

# church-registry API 설정
REGISTRY_BASE_URL = "https://church-registry.onrender.com"
# REGISTRY_BASE_URL = "http://localhost:5000"  # 로컬 테스트용

# 페이지 설정
PAGE_SIZE = 100
DELAY_BETWEEN_PAGES = 0.5
DELAY_BETWEEN_PHOTOS = 0.1

# 사진 저장 폴더
PHOTO_DIR = Path(__file__).parent / "photos"


def create_payload(page: int = 1, page_size: int = PAGE_SIZE, search_name: str = "") -> dict:
    """API 요청 페이로드 생성"""
    return {
        "paramName": search_name,
        "paramEName": "",
        "paramIds": "",
        "paramFree1": "",
        "paramFree2": "",
        "paramFree3": "",
        "paramFree4": "",
        "paramFree5": "",
        "paramFree6": "",
        "paramFree7": "",
        "paramFree8": "",
        "paramFree9": "",
        "paramFree10": "",
        "paramFree11": "",
        "paramFree12": "",
        "paramRange": "",
        "paramRange1": "",
        "paramRange2": "",
        "paramRange3": "",
        "paramRvname": "",
        "paramSection1": "",
        "paramSection2": "",
        "paramSection3": "",
        "paramSection4": "",
        "paramRvname2": "",
        "paramCoreChk": "",
        "paramCarNum": "",
        "paramGJeon": "",
        "paramLastSchool": "",
        "paramOffName": "",
        "paramGJeon1": "",
        "paramCvname": "",
        "paramCvname1": "",
        "paramState": "",
        "paramState1": "",
        "paramState3": "",
        "encryptOpt": "ALL",
        "rangeLimitUse": "false",
        "paramPage": str(page),
        "paramPageSize": str(page_size),
        "paramOrder": "NAME",
        "paramOrder2": "",
        "paramOrderAsc": "ASC",
        "paramOrder2Asc": "ASC",
        "paramPType": "P",
        "paramAddr": "",
        "paramRegDateS": "",
        "paramRegDateE": "",
    }


def fetch_page(session: requests.Session, page: int, page_size: int = PAGE_SIZE) -> dict:
    """한 페이지 데이터 가져오기"""
    headers = {
        "Content-Type": "application/json; charset=UTF-8",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": GOD4U_BASE_URL,
        "Referer": f"{GOD4U_BASE_URL}/WebMobile/WebChurch/RangeList.cshtml",
    }

    payload = create_payload(page=page, page_size=page_size)
    response = session.post(GOD4U_API_URL, json=payload, headers=headers)
    response.raise_for_status()

    data = response.json()
    if "d" in data:
        return json.loads(data["d"])
    return data


def download_photo(session: requests.Session, member_id: str) -> bytes | None:
    """프로필 사진 다운로드"""
    try:
        url = f"{GOD4U_PHOTO_URL}?id={member_id}"
        headers = {
            "Referer": f"{GOD4U_BASE_URL}/WebMobile/WebChurch/RangeList.cshtml",
        }
        response = session.get(url, headers=headers, timeout=10)

        # 이미지인지 확인 (Content-Type 또는 매직 바이트)
        content_type = response.headers.get("Content-Type", "")
        if "image" in content_type or response.content[:4] in [b'\xff\xd8\xff\xe0', b'\x89PNG', b'GIF8']:
            return response.content
        return None
    except Exception as e:
        return None


def crawl_all(cookies: dict = None, download_photos: bool = False) -> list:
    """전체 교적 크롤링"""
    if cookies is None:
        cookies = COOKIES

    session = requests.Session()
    session.cookies.update(cookies)

    all_persons = []

    # 첫 페이지로 전체 개수 확인
    print("🔍 전체 교인 수 확인 중...")
    first_page = fetch_page(session, page=1, page_size=PAGE_SIZE)

    total_count = int(first_page.get("totalcount", 0))
    total_pages = int(first_page.get("totalpage", 1))

    print(f"📊 전체 교인: {total_count}명, 총 페이지: {total_pages}")

    # 첫 페이지 데이터 추가
    persons = first_page.get("personInfo", [])
    all_persons.extend(persons)
    print(f"   페이지 1/{total_pages} 완료 ({len(persons)}명)")

    # 나머지 페이지 크롤링
    for page in range(2, total_pages + 1):
        time.sleep(DELAY_BETWEEN_PAGES)
        try:
            page_data = fetch_page(session, page=page, page_size=PAGE_SIZE)
            persons = page_data.get("personInfo", [])
            all_persons.extend(persons)
            print(f"   페이지 {page}/{total_pages} 완료 ({len(persons)}명)")
        except Exception as e:
            print(f"   ⚠️ 페이지 {page} 오류: {e}")
            continue

    print(f"\n✅ 크롤링 완료: 총 {len(all_persons)}명")

    # 사진 다운로드
    if download_photos:
        print("\n📸 사진 다운로드 중...")
        PHOTO_DIR.mkdir(exist_ok=True)

        photo_count = 0
        for i, person in enumerate(all_persons):
            member_id = person.get("id")
            if not member_id:
                continue

            photo_data = download_photo(session, member_id)
            if photo_data:
                photo_path = PHOTO_DIR / f"{member_id}.jpg"
                with open(photo_path, "wb") as f:
                    f.write(photo_data)
                person["_photo_path"] = str(photo_path)
                person["_photo_base64"] = base64.b64encode(photo_data).decode("utf-8")
                photo_count += 1

            if (i + 1) % 100 == 0:
                print(f"   {i + 1}/{len(all_persons)} 처리 완료 (사진 {photo_count}개)")

            time.sleep(DELAY_BETWEEN_PHOTOS)

        print(f"✅ 사진 다운로드 완료: {photo_count}개")

    return all_persons


def upload_to_registry(persons: list, with_photos: bool = True) -> dict:
    """church-registry에 업로드"""
    print(f"\n🚀 church-registry에 업로드 중...")
    print(f"   대상: {REGISTRY_BASE_URL}")

    results = {"success": 0, "failed": 0, "skipped": 0, "errors": []}

    for i, person in enumerate(persons):
        try:
            # 데이터 매핑 (god4u → church-registry)
            member_data = {
                "name": person.get("name", ""),
                "phone": person.get("handphone", "") or person.get("tel", ""),
                "email": person.get("email", ""),
                "address": person.get("addr", ""),
                "birth_date": person.get("birth", ""),
                "gender": "M" if person.get("sex") == "남" else "F" if person.get("sex") == "여" else "",
                "registration_date": person.get("regday", ""),
                "position": person.get("cvname1") or person.get("cvname", ""),  # 직분
                "status": "active" if person.get("state3") == "예배출석" else "inactive",
                "notes": f"god4u ID: {person.get('id')}\n가족: {person.get('ran1', '')}\n차량: {person.get('carnum', '')}",
                "external_id": person.get("id"),  # god4u 교적번호
            }

            # 빈 값 제거
            member_data = {k: v for k, v in member_data.items() if v}

            # 기존 회원 확인 (external_id로)
            check_url = f"{REGISTRY_BASE_URL}/api/members/by-external-id/{person.get('id')}"
            check_resp = requests.get(check_url, timeout=10)

            if check_resp.status_code == 200:
                # 기존 회원 업데이트
                existing = check_resp.json()
                member_id = existing.get("id")
                update_url = f"{REGISTRY_BASE_URL}/api/members/{member_id}"
                resp = requests.put(update_url, json=member_data, timeout=10)
            else:
                # 새 회원 등록
                create_url = f"{REGISTRY_BASE_URL}/api/members"
                resp = requests.post(create_url, json=member_data, timeout=10)

            if resp.status_code in [200, 201]:
                member_id = resp.json().get("id") or resp.json().get("member", {}).get("id")

                # 사진 업로드
                if with_photos and person.get("_photo_base64") and member_id:
                    try:
                        photo_url = f"{REGISTRY_BASE_URL}/api/members/{member_id}/photo"
                        photo_resp = requests.post(
                            photo_url,
                            json={"photo": person["_photo_base64"]},
                            timeout=30
                        )
                    except:
                        pass

                results["success"] += 1
            else:
                results["failed"] += 1
                results["errors"].append(f"{person.get('name')}: {resp.status_code}")

        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"{person.get('name')}: {str(e)}")

        if (i + 1) % 50 == 0:
            print(f"   {i + 1}/{len(persons)} 처리 완료 (성공: {results['success']}, 실패: {results['failed']})")

    print(f"\n✅ 업로드 완료!")
    print(f"   성공: {results['success']}명")
    print(f"   실패: {results['failed']}명")

    return results


# =============================================================================
# god4u로 데이터 동기화 (church-registry → god4u)
# =============================================================================

GOD4U_UPDATE_URL = f"{GOD4U_BASE_URL}/WebMobile/WebChurch/PersonModifyDetailExecute.cshtml"


def sync_to_god4u(member_data: dict, cookies: dict = None) -> bool:
    """
    church-registry 데이터를 god4u로 동기화

    Args:
        member_data: church-registry 형식의 회원 데이터
            - external_id: god4u 교적번호 (필수)
            - name, phone, email, address, birth_date, gender 등
        cookies: god4u 인증 쿠키

    Returns:
        성공 여부
    """
    if cookies is None:
        cookies = COOKIES

    external_id = member_data.get("external_id")
    if not external_id:
        print(f"⚠️ external_id가 없습니다: {member_data.get('name')}")
        return False

    session = requests.Session()
    session.cookies.update(cookies)

    # 주소 파싱 (전체 주소를 분리)
    address = member_data.get("address", "")
    sido, gugun, dong, bunji = "", "", "", ""
    if address:
        parts = address.split()
        if len(parts) >= 1:
            sido = parts[0]
        if len(parts) >= 2:
            gugun = parts[1]
        if len(parts) >= 3:
            dong = parts[2]
        if len(parts) >= 4:
            bunji = " ".join(parts[3:])

    # 성별 변환
    gender = member_data.get("gender", "")
    if gender in ["M", "male", "남성"]:
        gender = "남"
    elif gender in ["F", "female", "여성"]:
        gender = "여"

    # god4u 형식의 페이로드 생성
    payload = {
        "mode": "mod",
        "hidIdM": external_id,
        "txtHidM": external_id,
        "txtNameM": member_data.get("name", ""),
        "txtHandphoneM": member_data.get("phone", ""),
        "txtTelM": "",
        "txtEmailM": member_data.get("email", ""),
        "txtBirthDayM": member_data.get("birth_date", ""),
        "ddlGenderM": gender,
        "txtZipcodeM": member_data.get("zipcode", ""),
        "txtSidoM": sido,
        "txtGugunM": gugun,
        "txtDongM": dong,
        "txtBunjiM": bunji,
        "ddlState3": "예배출석" if member_data.get("status") == "active" else "결석",
        "txtRegDayM": member_data.get("registration_date", ""),
        # 기존 값 유지를 위한 필드들 (빈 값으로 두면 기존 값 유지)
        "hidRange": "",
        "hidRange1": "",
        "hidRange2": "",
        "hidRange3": "",
        "hidcvname": member_data.get("position", "") or member_data.get("member_type", ""),
        "hidcvname1": "",
        "hidstate": "교인",
        "hidstate1": "장년",
        "txtENameF": "",
        "txtENameM": "",
        "txtENameL": "",
        "ddlSolarM": "양",
        "txtAgeM": "",
        "txtCoreM": member_data.get("name", ""),
        "ddlRelative": "본인",
        "txtLeaderidM": "0",
        "txtLeaderM": "",
        "txtCarKind": "",
        "txtCarNum": "",
        "txtCarKind1": "",
        "txtCarNum1": "",
        "txPrechurchM": "",
        "txtEtcM": member_data.get("notes", ""),
        # Org 필드들 (원래 값 - 변경 감지용)
        "txtZipcodeMOrg": "",
        "txtSidoMOrg": "",
        "txtGugunMOrg": "",
        "txtDongMOrg": "",
        "txtBunjiMOrg": "",
        "txtCityM": "",
        "txtStM": "",
        "txtCityMOrg": "",
        "txtStMOrg": "",
        "ddlGYear": "2026",
        "txtRangeOrg": "",
        "txtRange1Org": "",
        "txtRange2Org": "",
        "txtRange3Org": "",
        "ddlCvAct": "",
        "txtCvDay": "",
        "txtAppointChurch": "",
        "txtCvnameOrg": "",
        "txtCvname1Org": "",
        "txtCvActorg": "",
        "txtCvDayOrg": "",
        "txtAppointChurchOrg": "",
        "txtStateDay": "",
        "txtStateOrg": "교인",
        "txtState1Org": "장년",
        "txtState3Org": "예배출석",
        "txtStateDayOrg": "",
        "hidvaccinename": "",
        "hidvaccinenumber": "",
        "txtVaccineDate": "",
        "txtVaccineNameOrg": "",
        "txtVaccineNumberOrg": "",
        "txtVaccineDateOrg": "",
        "txtVaccineIndex": "0",
        "txtOffnameM": "",
        "txtOfftelM": "",
        "ddlGrade": "",
        "txtBaptday": "",
        "txtBaptchurch": "",
        "txtBaptist": "",
        "txtGradeOrg": "",
        "txtBaptdayOrg": "",
        "txtBaptchurchOrg": "",
        "txtBaptistOrg": "",
        "txtFree1": "",
        "txtFree2": "",
        "txtFree3": "",
        "txtFree4": "",
        "txtFree5": "",
        "txtFree6": "",
        "txtFree7": "",
        "txtFree8": "",
        "txtFree9": "",
        "txtFree10": "",
        "txtFree11": "",
        "txtFree12": "",
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Accept": "text/html, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": GOD4U_BASE_URL,
        "Referer": f"{GOD4U_BASE_URL}/WebMobile/WebChurch/PersonModifyDetail.cshtml?id={external_id}",
    }

    try:
        response = session.post(GOD4U_UPDATE_URL, data=payload, headers=headers, timeout=30)

        # 성공 여부 확인 (응답에 "정보수정 완료" 포함)
        if response.status_code == 200 and "정보수정 완료" in response.text:
            return True
        else:
            print(f"⚠️ god4u 업데이트 실패: {member_data.get('name')} (status: {response.status_code})")
            return False

    except Exception as e:
        print(f"❌ god4u 업데이트 오류: {member_data.get('name')} - {str(e)}")
        return False


def sync_registry_to_god4u(cookies: dict = None) -> dict:
    """
    church-registry의 모든 회원을 god4u로 동기화
    (external_id가 있는 회원만)
    """
    print("\n🔄 church-registry → god4u 동기화 시작...")

    results = {"success": 0, "failed": 0, "skipped": 0, "errors": []}

    # church-registry에서 회원 목록 가져오기
    try:
        resp = requests.get(f"{REGISTRY_BASE_URL}/api/members", timeout=30)
        if resp.status_code != 200:
            print(f"❌ church-registry 조회 실패: {resp.status_code}")
            return results

        members = resp.json().get("members", [])
        print(f"📊 church-registry 회원: {len(members)}명")

    except Exception as e:
        print(f"❌ church-registry 연결 실패: {str(e)}")
        return results

    # god4u로 동기화
    for i, member in enumerate(members):
        external_id = member.get("external_id")

        if not external_id:
            results["skipped"] += 1
            continue

        if sync_to_god4u(member, cookies):
            results["success"] += 1
        else:
            results["failed"] += 1
            results["errors"].append(member.get("name", "Unknown"))

        if (i + 1) % 50 == 0:
            print(f"   {i + 1}/{len(members)} 처리 완료")

        time.sleep(0.5)  # API 부하 방지

    print(f"\n✅ 동기화 완료!")
    print(f"   성공: {results['success']}명")
    print(f"   실패: {results['failed']}명")
    print(f"   건너뜀 (external_id 없음): {results['skipped']}명")

    return results


def save_to_csv(persons: list, filename: str = None) -> str:
    """CSV 파일로 저장"""
    if not persons:
        return None

    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"교적_{timestamp}.csv"

    output_path = Path(__file__).parent / filename

    # 출력 필드
    fields = [
        ("id", "교적번호"),
        ("name", "이름"),
        ("sex", "성별"),
        ("birth", "생년월일"),
        ("age", "나이"),
        ("cvname", "직분1"),
        ("cvname1", "직분2"),
        ("handphone", "핸드폰"),
        ("tel", "전화"),
        ("addr", "주소"),
        ("zipcode", "우편번호"),
        ("email", "이메일"),
        ("state", "상태"),
        ("state1", "그룹"),
        ("state3", "출석상태"),
        ("regday", "등록일"),
        ("ran1", "가족"),
        ("carnum", "차량번호"),
        ("etc", "기타"),
    ]

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        headers = [display_name for _, display_name in fields]
        writer.writerow(headers)

        for person in persons:
            row = [person.get(field_name, "") or "" for field_name, _ in fields]
            writer.writerow(row)

    print(f"💾 CSV 저장: {output_path}")
    return str(output_path)


def save_to_json(persons: list, filename: str = None) -> str:
    """JSON 파일로 저장"""
    if not persons:
        return None

    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"교적_{timestamp}.json"

    output_path = Path(__file__).parent / filename

    # base64 사진 데이터는 제외
    clean_persons = []
    for p in persons:
        clean_p = {k: v for k, v in p.items() if not k.startswith("_")}
        clean_persons.append(clean_p)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(clean_persons, f, ensure_ascii=False, indent=2)

    print(f"💾 JSON 저장: {output_path}")
    return str(output_path)


def main():
    """메인 실행"""
    import argparse

    parser = argparse.ArgumentParser(description="교적 크롤링 및 양방향 동기화")
    parser.add_argument("--no-photos", action="store_true", help="사진 다운로드 건너뛰기")
    parser.add_argument("--upload", action="store_true", help="church-registry에 업로드 (god4u → registry)")
    parser.add_argument("--csv-only", action="store_true", help="CSV만 저장 (사진/업로드 없음)")
    parser.add_argument("--sync-to-god4u", action="store_true", help="church-registry → god4u 동기화")
    parser.add_argument("--full-sync", action="store_true", help="양방향 전체 동기화 (god4u ↔ registry)")
    args = parser.parse_args()

    print("=" * 60)

    # church-registry → god4u 동기화만 실행
    if args.sync_to_god4u:
        print("🔄 church-registry → god4u 동기화")
        print("=" * 60)
        sync_registry_to_god4u()
        print("\n" + "=" * 60)
        print("🎉 완료!")
        print("=" * 60)
        return

    # 양방향 전체 동기화
    if args.full_sync:
        print("🔄 양방향 전체 동기화 (god4u ↔ church-registry)")
        print("=" * 60)

        # 1. god4u → church-registry
        print("\n[1/2] god4u → church-registry")
        persons = crawl_all(download_photos=True)
        if persons:
            upload_to_registry(persons, with_photos=True)

        # 2. church-registry → god4u (새로 추가된 회원만)
        print("\n[2/2] church-registry → god4u")
        sync_registry_to_god4u()

        print("\n" + "=" * 60)
        print("🎉 양방향 동기화 완료!")
        print("=" * 60)
        return

    # 기본: god4u 크롤링
    print("🏛️  교적 크롤링 시작")
    print("=" * 60)

    download_photos = not args.no_photos and not args.csv_only

    # 크롤링 실행
    persons = crawl_all(download_photos=download_photos)

    if persons:
        # 파일 저장
        save_to_csv(persons)
        save_to_json(persons)

        # church-registry 업로드
        if args.upload:
            upload_to_registry(persons, with_photos=download_photos)

    print("\n" + "=" * 60)
    print("🎉 완료!")
    print("=" * 60)


if __name__ == "__main__":
    main()
