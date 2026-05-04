"""
KRX 반도체 지수 + 비트코인 KRW 가격을 일별로 수집해 CSV로 저장.
2014-01-01 ~ 오늘.
"""
from datetime import datetime, timedelta
import time
import pandas as pd
import requests
from pykrx import stock

START_DATE = "20140101"
TODAY = datetime.now().strftime("%Y%m%d")
OUTPUT_CSV = "cycle_data.csv"


def find_krx_semi_ticker():
    """KRX 시리즈 중 '반도체'가 들어간 지수 코드를 동적으로 찾는다."""
    tickers = stock.get_index_ticker_list(market="KRX")
    for t in tickers:
        name = stock.get_index_ticker_name(t)
        if "반도체" in name:
            print(f"[KRX] 발견: {t} = {name}")
            return t, name
    raise RuntimeError("KRX 반도체 지수를 찾지 못함")


def fetch_krx_semi():
    ticker, name = find_krx_semi_ticker()
    print(f"[KRX] {START_DATE} ~ {TODAY} 데이터 수집 중... (1~2분 소요)")
    df = stock.get_index_ohlcv(START_DATE, TODAY, ticker)
    df = df[["종가"]].rename(columns={"종가": "krx_semi"})
    df.index = pd.to_datetime(df.index).date
    df.index.name = "date"
    print(f"[KRX] {len(df)}일 데이터 수집 완료")
    return df


def fetch_btc_krw():
    """업비트 일봉 API로 BTC/KRW 전체 기간 수집. 200개씩 페이징."""
    print("[BTC] 업비트 일봉 수집 시작...")
    all_rows = []
    to_param = None
    target_start = datetime.strptime(START_DATE, "%Y%m%d")

    while True:
        url = "https://api.upbit.com/v1/candles/days"
        params = {"market": "KRW-BTC", "count": 200}
        if to_param:
            params["to"] = to_param

        for attempt in range(3):
            try:
                r = requests.get(url, params=params, timeout=10)
                r.raise_for_status()
                rows = r.json()
                break
            except Exception as e:
                print(f"[BTC] 재시도 {attempt + 1}/3: {e}")
                time.sleep(2)
        else:
            raise RuntimeError("[BTC] 업비트 호출 실패")

        if not rows:
            break

        all_rows.extend(rows)
        oldest = datetime.strptime(
            rows[-1]["candle_date_time_utc"], "%Y-%m-%dT%H:%M:%S"
        )
        if oldest < target_start or len(rows) < 200:
            break
        to_param = (oldest - timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        time.sleep(0.15)

    df = pd.DataFrame(all_rows)[["candle_date_time_kst", "trade_price"]]
    df.columns = ["date", "btc_krw"]
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df = df.set_index("date").sort_index()
    df = df[df.index >= datetime.strptime(START_DATE, "%Y%m%d").date()]
    df = df[~df.index.duplicated(keep="first")]
    print(f"[BTC] {len(df)}일 데이터 수집 완료")
    return df


def main():
    krx = fetch_krx_semi()
    btc = fetch_btc_krw()

    df = krx.join(btc, how="outer").sort_index()
    df["krx_semi"] = df["krx_semi"].ffill()
    df["btc_krw"] = df["btc_krw"].ffill()
    df = df.dropna()

    df.to_csv(OUTPUT_CSV)
    print(f"\n[완료] {OUTPUT_CSV} 저장")
    print(f"  기간: {df.index.min()} ~ {df.index.max()}")
    print(f"  행 수: {len(df)}")
    print(f"  최신값: KRX={df['krx_semi'].iloc[-1]:,.2f}, "
          f"BTC={df['btc_krw'].iloc[-1]:,.0f}원")


if __name__ == "__main__":
    main()
