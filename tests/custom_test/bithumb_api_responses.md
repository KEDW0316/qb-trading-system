# Bithumb API 실제 응답 데이터 문서

생성 시간: 2025-08-26 00:27:13

이 문서는 실제 API 호출 결과를 바탕으로 작성되었습니다.

## get_market_list

**설명**: 마켓 리스트 조회 - 거래 가능한 모든 마켓 정보

**함수 호출**: `get_market_list()`

**입력 파라미터**:
```json
"없음"
```

**응답 타입**: list

**응답 길이**: 31208 문자

**캡처 시간**: 2025-08-26T00:27:13.142161

**응답 데이터**:
```json
[
  {
    "market": "KRW-BTC",
    "korean_name": "비트코인",
    "english_name": "Bitcoin"
  },
  {
    "market": "KRW-ETH",
    "korean_name": "이더리움",
    "english_name": "Ethereum"
  },
  {
    "market": "KRW-ETC",
    "korean_name": "이더리움 클래식",
    "english_name": "Ethereum Classic"
  },
  {
    "market": "KRW-XRP",
    "korean_name": "엑스알피 [리플]",
    "english_name": "XRP"
  },
  {
    "market": "KRW-BCH",
    "korean_name": "비트코인 캐시",
    "english_name": "Bitcoin Cash"
  },
  {
    "market": "KRW-QTUM",
    "korean_name": "퀀텀",
    "english_name": "Qtum"
  },
  {
    "market": "KRW-A",
    "korean_name": "볼타",
    "english_name": "Vaulta"
  },
  {
    "market": "KRW-ICX",
    "korean_name": "아이콘",
    "english_name": "ICON"
  },
  {
    "market": "KRW-TRX",
    "korean_name": "트론",
    "english_name": "TRON"
  },
  {
    "market": "KRW-ELF",
    "korean_name": "엘프",
    "english_name": "aelf"
  },
  {
    "market": "KRW-KNC",
    "korean_name": "카이버 네트워크",
    "english_name": "Kyber Network"
  },
  {
    "market": "KRW-GLM",
    "korean_name": "골렘",
    "english_name": "Golem"
  },
  {
    "market": "KRW-ZIL",
    "korean_name": "질리카",
    "english_name": "Zilliqa"
  },
  {
    "market": "KRW-WAXP",
    "korean_name": "왁스",
    "english_name": "WAXP"
  },
  {
    "market": "KRW-POWR",
    "korean_name": "파워렛저",
    "english_name": "Powerledger"
  },
  {
    "market": "KRW-LRC",
    "korean_name": "루프링",
    "english_name": "Loopring"
  },
  {
    "market": "KRW-STEEM",
    "korean_name": "스팀",
    "english_name": "Steem"
  },
  {
    "market": "KRW-ZRX",
    "korean_name": "제로엑스",
    "english_name": "0x"
  },
  {
    "market": "KRW-SNT",
    "korean_name": "스테이터스네트워크토큰",
    "english_name": "Status Network"
  },
  {
    "market": "KRW-ADA",
    "korean_name": "에이다",
    "english_name": "Cardano"
  },
  {
    "market": "KRW-CTXC",
    "korean_name": "코르텍스",
    "english_name": "Cortex"
  },
  {
    "market": "KRW-BAT",
    "korean_name": "베이직어텐션토큰",
    "english_name": "Basic Attention Token"
  },
  {
    "market": "KRW-THETA",
    "korean_name": "쎄타토큰",
    "english_name": "Theta Token"
  },
  {
    "market": "KRW-CVC",
    "korean_name": "시빅",
    "english_name": "Civic"
  },
  {
    "market": "KRW-WAVES",
    "korean_name": "웨이브",
    "english_name": "Waves"
  },
  {
    "market": "KRW-LINK",
    "korean_name": "체인링크",
    "english_name": "ChainLink"
  },
  {
    "market": "KRW-ENJ",
    "korean_name": "엔진코인",
    "english_name": "Enjin Coin"
  },
  {
    "market": "KRW-VET",
    "korean_name": "비체인",
    "english_name": "VeChain"
  },
  {
    "market": "KRW-MTL",
    "korean_name": "메탈",
    "english_name": "Metal"
  },
  {
    "market": "KRW-IOST",
    "korean_name": "이오스트",
    "english_name": "IOST"
  },
  {
    "market": "KRW-AMO",
    "korean_name": "아모코인",
    "english_name": "AMO Coin"
  },
  {
    "market": "KRW-BSV",
    "korean_name": "비트코인에스브이",
    "english_name": "BITCOINSV"
  },
  {
    "market": "KRW-ORBS",
    "korean_name": "오브스",
    "english_name": "Orbs"
  },
  {
    "market": "KRW-TFUEL",
    "korean_name": "쎄타퓨엘",
    "english_name": "TFUEL"
  },
  {
    "market": "KRW-ANKR",
    "korean_name": "앵커",
    "english_name": "Ankr Network"
  },
  {
    "market": "KRW-MIX",
    "korean_name": "믹스마블",
    "english_name": "MixMarvel Token"
  },
  {
    "market": "KRW-CRO",
    "korean_name": "크로노스",
    "english_name": "Cronos"
  },
  {
    "market": "KRW-CHR",
    "korean_name": "크로미아",
    "english_name": "Chromia"
  },
  {
    "market": "KRW-MBL",
    "korean_name": "무비블록",
    "english_name": "MovieBloc"
  },
  {
    "market": "KRW-FCT2",
    "korean_name": "피르마체인",
    "english_name": "Firmachain"
  },
  {
    "market": "KRW-BOA",
    "korean_name": "보아",
    "english_name": "BOSagora"
  },
  {
    "market": "KRW-MEV",
    "korean_name": "미버스",
    "english_name": "MEVerse"
  },
  {
    "market": "KRW-SXP",
    "korean_name": "솔라",
    "english_name": "Solar"
  },
  {
    "market": "KRW-COS",
    "korean_name": "콘텐토스",
    "english_name": "Contentos"
  },
  {
    "market": "KRW-EL",
    "korean_name": "엘리시아",
    "english_name": "ELYSIA"
  },
  {
    "market": "KRW-HIVE",
    "korean_name": "하이브",
    "english_name": "Hive"
  },
  {
    "market": "KRW-XPR",
    "korean_name": "엑스피알 네트워크",
    "english_name": "XPR Network"
  },
  {
    "market": "KRW-EGG",
    "korean_name": "네스트리",
    "english_name": "Nestree"
  },
  {
    "market": "KRW-BORA",
    "korean_name": "보라",
    "english_name": "BORA"
  },
  {
    "market": "KRW-ARPA",
    "korean_name": "알파",
    "english_name": "ARPA"
  },
  {
    "market": "KRW-CTC",
    "korean_name": "크레딧코인",
    "english_name": "Creditcoin"
  },
  {
    "market": "KRW-APM",
    "korean_name": "에이피엠 코인",
    "english_name": "apM Coin"
  },
  {
    "market": "KRW-CKB",
    "korean_name": "너보스",
    "english_name": "Nervos Network"
  },
  {
    "market": "KRW-AERGO",
    "korean_name": "아르고",
    "english_name": "Aergo"
  },
  {
    "market": "KRW-EVZ",
    "korean_name": "이브이지",
    "english_name": "Electronic Vehicle Zone"
  },
  {
    "market": "KRW-UNI",
    "korean_name": "유니스왑",
    "english_name": "Uniswap"
  },
  {
    "market": "KRW-YFI",
    "korean_name": "연파이낸스",
    "english_name": "yearn.finance"
  },
  {
    "market": "KRW-UMA",
    "korean_name": "우마",
    "english_name": "UMA"
  },
  {
    "market": "KRW-AAVE",
    "korean_name": "에이브",
    "english_name": "Aave"
  },
  {
    "market": "KRW-COMP",
    "korean_name": "컴파운드",
    "english_name": "Compound"
  },
  {
    "market": "KRW-BAL",
    "korean_name": "밸런서",
    "english_name": "Balancer"
  },
  {
    "market": "KRW-RSR",
    "korean_name": "리저브라이트",
    "english_name": "Reserve Rights"
  },
  {
    "market": "KRW-NMR",
    "korean_name": "뉴메레르",
    "english_name": "Numeraire"
  },
  {
    "market": "KRW-RLC",
    "korean_name": "아이젝",
    "english_name": "iExec RLC"
  },
  {
    "market": "KRW-UOS",
    "korean_name": "울트라",
    "english_name": "Ultra"
  },
  {
    "market": "KRW-SAND",
    "korean_name": "샌드박스",
    "english_name": "The Sandbox"
  },
  {
    "market": "KRW-AWE",
    "korean_name": "에이더블유이",
    "english_name": "AWE Network"
  },
  {
    "market": "KRW-BEL",
    "korean_name": "벨라프로토콜",
    "english_name": "Bella Protocol"
  },
  {
    "market": "KRW-OBSR",
    "korean_name": "옵저버",
    "english_name": "Observer"
  },
  {
    "market": "KRW-POLA",
    "korean_name": "폴라리스 쉐어",
    "english_name": "Polaris Share"
  },
  {
    "market": "KRW-ADP",
    "korean_name": "어댑터 토큰",
    "english_name": "Adappter Token"
  },
  {
    "market": "KRW-DVI",
    "korean_name": "디비전",
    "english_name": "Dvision Network"
  },
  {
    "market": "KRW-GHX",
    "korean_name": "게이머코인",
    "english_name": "Gamercoin"
  },
  {
    "market": "KRW-CBK",
    "korean_name": "코박토큰",
    "english_name": "Cobak Token"
  },
  {
    "market": "KRW-MVC",
    "korean_name": "마일벌스",
    "english_name": "MileVerse"
  },
  {
    "market": "KRW-BLY",
    "korean_name": "블로서리",
    "english_name": "Blocery"
  },
  {
    "market": "KRW-GRT",
    "korean_name": "더그래프",
    "english_name": "The Graph"
  },
  {
    "market": "KRW-BIOT",
    "korean_name": "바이오패스포트",
    "english_name": "BioPassport"
  },
  {
    "market": "KRW-SNX",
    "korean_name": "신세틱스",
    "english_name": "Synthetix Network Token"
  },
  {
    "market": "KRW-SOFI",
    "korean_name": "라이파이낸스",
    "english_name": "Rai Finance"
  },
  {
    "market": "KRW-GRACY",
    "korean_name": "그레이시",
    "english_name": "Gracy"
  },
  {
    "market": "KRW-OXT",
    "korean_name": "오키드",
    "english_name": "Orchid"
  },
  {
    "market": "KRW-MAPO",
    "korean_name": "맵프로토콜",
    "english_name": "MAP Protocol"
  },
  {
    "market": "KRW-AQT",
    "korean_name": "알파쿼크",
    "english_name": "Alpha Quark Token"
  },
  {
    "market": "KRW-WIKEN",
    "korean_name": "위드",
    "english_name": "Project WITH"
  },
  {
    "market": "KRW-CTSI",
    "korean_name": "카르테시",
    "english_name": "Cartesi"
  },
  {
    "market": "KRW-MANA",
    "korean_name": "디센트럴랜드",
    "english_name": "Decentraland"
  },
  {
    "market": "KRW-LPT",
    "korean_name": "라이브피어",
    "english_name": "Livepeer"
  },
  {
    "market": "KRW-SUSHI",
    "korean_name": "스시스왑",
    "english_name": "Sushiswap"
  },
  {
    "market": "KRW-PUNDIX",
    "korean_name": "펀디엑스",
    "english_name": "Pundi X"
  },
  {
    "market": "KRW-CELR",
    "korean_name": "셀러네트워크",
    "english_name": "Celer Network"
  },
  {
    "market": "KRW-SLF",
    "korean_name": "셀프 체인",
    "english_name": "Self Chain"
  },
  {
    "market": "KRW-BFC",
    "korean_name": "바이프로스트",
    "english_name": "Bifrost"
  },
  {
    "market": "KRW-ALICE",
    "korean_name": "마이네이버앨리스",
    "english_name": "MyNeighborAlice"
  },
  {
    "market": "KRW-OGN",
    "korean_name": "오리진프로토콜",
    "english_name": "Origin Protocol"
  },
  {
    "market": "KRW-COTI",
    "korean_name": "코티",
    "english_name": "COTI"
  },
  {
    "market": "KRW-CAKE",
    "korean_name": "팬케이크스왑",
    "english_name": "PancakeSwap"
  },
  {
    "market": "KRW-BNT",
    "korean_name": "뱅코르",
    "english_name": "Bancor"
  },
  {
    "market": "KRW-XVS",
    "korean_name": "비너스",
    "english_name": "Venus"
  },
  {
    "market": "KRW-SWAP",
    "korean_name": "트러스트스왑",
    "english_name": "TrustSwap"
  },
  {
    "market": "KRW-CHZ",
    "korean_name": "칠리즈",
    "english_name": "Chiliz"
  },
  {
    "market": "KRW-AXS",
    "korean_name": "엑시인피니티",
    "english_name": "Axie Infinity"
  },
  {
    "market": "KRW-DAO",
    "korean_name": "다오메이커",
    "english_name": "DAO Maker"
  },
  {
    "market": "KRW-SIX",
    "korean_name": "식스",
    "english_name": "SIX"
  },
  {
    "market": "KRW-USDS",
    "korean_name": "유에스디에스",
    "english_name": "USDS"
  },
  {
    "market": "KRW-SHIB",
    "korean_name": "시바이누",
    "english_name": "SHIBA INU"
  },
  {
    "market": "KRW-POL",
    "korean_name": "폴리곤 에코시스템 토큰",
    "english_name": "Polygon Ecosystem Token"
  },
  {
    "market": "KRW-WOO",
    "korean_name": "우",
    "english_name": "WOO"
  },
  {
    "market": "KRW-ACH",
    "korean_name": "알케미페이",
    "english_name": "Alchemy Pay"
  },
  {
    "market": "KRW-XLM",
    "korean_name": "스텔라루멘",
    "english_name": "Stellar Lumens"
  },
  {
    "market": "KRW-ONT",
    "korean_name": "온톨로지",
    "english_name": "Ontology"
  },
  {
    "market": "KRW-META",
    "korean_name": "메타디움",
    "english_name": "Metadium"
  },
  {
    "market": "KRW-KAIA",
    "korean_name": "카이아",
    "english_name": "Kaia"
  },
  {
    "market": "KRW-ONG",
    "korean_name": "온톨로지가스",
    "english_name": "Ontology Gas"
  },
  {
    "market": "KRW-ALGO",
    "korean_name": "알고랜드",
    "english_name": "Algorand"
  },
  {
    "market": "KRW-JST",
    "korean_name": "저스트",
    "english_name": "JUST"
  },
  {
    "market": "KRW-XTZ",
    "korean_name": "테조스",
    "english_name": "Tezos"
  },
  {
    "market": "KRW-MLK",
    "korean_name": "밀크",
    "english_name": "MiL.k"
  },
  {
    "market": "KRW-DOT",
    "korean_name": "폴카닷",
    "english_name": "Polkadot"
  },
  {
    "market": "KRW-ATOM",
    "korean_name": "코스모스",
    "english_name": "Cosmos"
  },
  {
    "market": "KRW-TEMCO",
    "korean_name": "템코",
    "english_name": "TEMCO"
  },
  {
    "market": "KRW-DOGE",
    "korean_name": "도지코인",
    "english_name": "Dogecoin"
  },
  {
    "market": "KRW-KSM",
    "korean_name": "쿠사마",
    "english_name": "Kusama"
  },
  {
    "market": "KRW-CTK",
    "korean_name": "셴투",
    "english_name": "Shentu"
  },
  {
    "market": "KRW-BNB",
    "korean_name": "비앤비",
    "english_name": "BNB"
  },
  {
    "market": "KRW-NFT",
    "korean_name": "에이피이앤에프티",
    "english_name": "APENFT"
  },
  {
    "market": "KRW-SUN",
    "korean_name": "썬",
    "english_name": "SUN"
  },
  {
    "market": "KRW-XEC",
    "korean_name": "이캐시",
    "english_name": "eCash"
  },
  {
    "market": "KRW-SOL",
    "korean_name": "솔라나",
    "english_name": "Solana"
  },
  {
    "market": "KRW-EGLD",
    "korean_name": "멀티버스엑스",
    "english_name": "MultiversX"
  },
  {
    "market": "KRW-MASK",
    "korean_name": "마스크네트워크",
    "english_name": "Mask Network"
  },
  {
    "market": "KRW-C98",
    "korean_name": "코인98",
    "english_name": "Coin98"
  },
  {
    "market": "KRW-MED",
    "korean_name": "메디블록",
    "english_name": "MediBloc"
  },
  {
    "market": "KRW-1INCH",
    "korean_name": "1인치",
    "english_name": "1inch"
  },
  {
    "market": "KRW-CRV",
    "korean_name": "커브",
    "english_name": "Curve DAO Token"
  },
  {
    "market": "KRW-BOBA",
    "korean_name": "보바토큰",
    "english_name": "Boba Network"
  },
  {
    "market": "KRW-DYDX",
    "korean_name": "디와이디엑스",
    "english_name": "dYdX"
  },
  {
    "market": "KRW-MINA",
    "korean_name": "미나",
    "english_name": "Mina"
  },
  {
    "market": "KRW-FLOW",
    "korean_name": "플로우",
    "english_name": "Flow"
  },
  {
    "market": "KRW-JOE",
    "korean_name": "트레이더 조",
    "english_name": "JOE"
  },
  {
    "market": "KRW-GALA",
    "korean_name": "갈라",
    "english_name": "Gala"
  },
  {
    "market": "KRW-ENS",
    "korean_name": "이더리움네임서비스",
    "english_name": "Ethereum Name Service"
  },
  {
    "market": "KRW-BTT",
    "korean_name": "비트토렌트",
    "english_name": "BitTorrent"
  },
  {
    "market": "KRW-JASMY",
    "korean_name": "재스미코인",
    "english_name": "JasmyCoin"
  },
  {
    "market": "KRW-REQ",
    "korean_name": "리퀘스트",
    "english_name": "Request"
  },
  {
    "market": "KRW-CSPR",
    "korean_name": "캐스퍼",
    "english_name": "Casper"
  },
  {
    "market": "KRW-AVAX",
    "korean_name": "아발란체",
    "english_name": "Avalanche"
  },
  {
    "market": "KRW-TDROP",
    "korean_name": "티드랍",
    "english_name": "ThetaDrop"
  },
  {
    "market": "KRW-HBAR",
    "korean_name": "헤데라",
    "english_name": "Hedera"
  },
  {
    "market": "KRW-FANC",
    "korean_name": "팬시",
    "english_name": "fanC"
  },
  {
    "market": "KRW-MAY",
    "korean_name": "메이플라워",
    "english_name": "Mayflower"
  },
  {
    "market": "KRW-REI",
    "korean_name": "레이",
    "english_name": "REI"
  },
  {
    "market": "KRW-T",
    "korean_name": "쓰레스홀드",
    "english_name": "Threshold"
  },
  {
    "market": "KRW-MBX",
    "korean_name": "마브렉스",
    "english_name": "Marblex"
  },
  {
    "market": "KRW-GMT",
    "korean_name": "스테픈",
    "english_name": "STEPN"
  },
  {
    "market": "KRW-TAVA",
    "korean_name": "알타바",
    "english_name": "ALTAVA"
  },
  {
    "market": "KRW-D",
    "korean_name": "달 오픈 네트워크",
    "english_name": "DAR Open Network"
  },
  {
    "market": "KRW-APE",
    "korean_name": "에이프코인",
    "english_name": "ApeCoin"
  },
  {
    "market": "KRW-WNCG",
    "korean_name": "랩트 나인 크로니클 골드",
    "english_name": "Wrapped NCG"
  },
  {
    "market": "KRW-AL",
    "korean_name": "아치루트",
    "english_name": "ArchLoot"
  },
  {
    "market": "KRW-XCN",
    "korean_name": "오닉스코인",
    "english_name": "Onyxcoin"
  },
  {
    "market": "KRW-AZIT",
    "korean_name": "아지트",
    "english_name": "Azit"
  },
  {
    "market": "KRW-FLR",
    "korean_name": "플레어",
    "english_name": "Flare"
  },
  {
    "market": "KRW-SFP",
    "korean_name": "세이프팔",
    "english_name": "Safepal"
  },
  {
    "market": "KRW-FITFI",
    "korean_name": "스텝앱",
    "english_name": "Step App"
  },
  {
    "market": "KRW-STAT",
    "korean_name": "스탯",
    "english_name": "STAT"
  },
  {
    "market": "KRW-CRTS",
    "korean_name": "크라토스",
    "english_name": "Cratos"
  },
  {
    "market": "KRW-LBL",
    "korean_name": "레이블 에이아이",
    "english_name": "Lable AI"
  },
  {
    "market": "KRW-LM",
    "korean_name": "레저메타",
    "english_name": "LeisureMeta"
  },
  {
    "market": "KRW-GRND",
    "korean_name": "슈퍼워크",
    "english_name": "Superwalk"
  },
  {
    "market": "KRW-APT",
    "korean_name": "앱토스",
    "english_name": "Aptos"
  },
  {
    "market": "KRW-BLUR",
    "korean_name": "블러",
    "english_name": "Blur"
  },
  {
    "market": "KRW-OAS",
    "korean_name": "오아시스",
    "english_name": "Oasys"
  },
  {
    "market": "KRW-HOOK",
    "korean_name": "훅트 프로토콜",
    "english_name": "Hooked Protocol"
  },
  {
    "market": "KRW-LWA",
    "korean_name": "루미웨이브",
    "english_name": "Lumiwave"
  },
  {
    "market": "KRW-OP",
    "korean_name": "옵티미즘",
    "english_name": "Optimism"
  },
  {
    "market": "KRW-ROA",
    "korean_name": "로아코어",
    "english_name": "ROA CORE"
  },
  {
    "market": "KRW-GMX",
    "korean_name": "지엠엑스",
    "english_name": "GMX"
  },
  {
    "market": "KRW-STX",
    "korean_name": "스택스",
    "english_name": "Stacks"
  },
  {
    "market": "KRW-XPLA",
    "korean_name": "엑스플라",
    "english_name": "XPLA"
  },
  {
    "market": "KRW-AHT",
    "korean_name": "아하토큰",
    "english_name": "AhaToken"
  },
  {
    "market": "KRW-ARB",
    "korean_name": "아비트럼",
    "english_name": "Arbitrum"
  },
  {
    "market": "KRW-INJ",
    "korean_name": "인젝티브",
    "english_name": "Injective"
  },
  {
    "market": "KRW-HFT",
    "korean_name": "해시플로우",
    "english_name": "Hashflow"
  },
  {
    "market": "KRW-RPL",
    "korean_name": "로켓풀",
    "english_name": "Rocket Pool"
  },
  {
    "market": "KRW-IMX",
    "korean_name": "이뮤터블엑스",
    "english_name": "Immutable X"
  },
  {
    "market": "KRW-CFX",
    "korean_name": "콘플럭스",
    "english_name": "Conflux Network"
  },
  {
    "market": "KRW-ACS",
    "korean_name": "액세스프로토콜",
    "english_name": "Access Protocol"
  },
  {
    "market": "KRW-FXS",
    "korean_name": "프랙스 셰어",
    "english_name": "Frax Share"
  },
  {
    "market": "KRW-CELO",
    "korean_name": "셀로",
    "english_name": "Celo"
  },
  {
    "market": "KRW-LDO",
    "korean_name": "리도다오",
    "english_name": "Lido DAO"
  },
  {
    "market": "KRW-S",
    "korean_name": "소닉",
    "english_name": "Sonic"
  },
  {
    "market": "KRW-FET",
    "korean_name": "페치",
    "english_name": "Fetch.ai"
  },
  {
    "market": "KRW-SUI",
    "korean_name": "수이",
    "english_name": "SUI"
  },
  {
    "market": "KRW-NCT",
    "korean_name": "폴리스웜",
    "english_name": "Polyswarm"
  },
  {
    "market": "KRW-FLOKI",
    "korean_name": "플로키",
    "english_name": "FLOKI"
  },
  {
    "market": "KRW-ID",
    "korean_name": "스페이스 아이디",
    "english_name": "SPACE ID"
  },
  {
    "market": "KRW-RENDER",
    "korean_name": "렌더토큰",
    "english_name": "Render Token"
  },
  {
    "market": "KRW-STG",
    "korean_name": "스타게이트 파이낸스",
    "english_name": "Stargate Finance"
  },
  {
    "market": "KRW-OSMO",
    "korean_name": "오스모시스",
    "english_name": "Osmosis"
  },
  {
    "market": "KRW-FIL",
    "korean_name": "파일코인",
    "english_name": "Filecoin"
  },
  {
    "market": "KRW-ILV",
    "korean_name": "일루비움",
    "english_name": "Illuvium"
  },
  {
    "market": "KRW-MAV",
    "korean_name": "매버릭 프로토콜",
    "english_name": "Maverick Protocol"
  },
  {
    "market": "KRW-RSS3",
    "korean_name": "알에스에스쓰리",
    "english_name": "RSS3"
  },
  {
    "market": "KRW-AUDIO",
    "korean_name": "오디우스",
    "english_name": "Audius"
  },
  {
    "market": "KRW-AGI",
    "korean_name": "델리시움",
    "english_name": "Delysium"
  },
  {
    "market": "KRW-ASTR",
    "korean_name": "아스타",
    "english_name": "Astar"
  },
  {
    "market": "KRW-WLD",
    "korean_name": "월드코인",
    "english_name": "Worldcoin"
  },
  {
    "market": "KRW-FLUX",
    "korean_name": "플럭스",
    "english_name": "Flux"
  },
  {
    "market": "KRW-AGLD",
    "korean_name": "어드벤처골드",
    "english_name": "Adventure Gold"
  },
  {
    "market": "KRW-AR",
    "korean_name": "알위브",
    "english_name": "Arweave"
  },
  {
    "market": "KRW-RVN",
    "korean_name": "레이븐코인",
    "english_name": "Ravencoin"
  },
  {
    "market": "KRW-EDU",
    "korean_name": "오픈 캠퍼스",
    "english_name": "Open Campus"
  },
  {
    "market": "KRW-SEI",
    "korean_name": "세이",
    "english_name": "Sei"
  },
  {
    "market": "KRW-WAXL",
    "korean_name": "엑셀라",
    "english_name": "Axelar"
  },
  {
    "market": "KRW-MOC",
    "korean_name": "모스코인",
    "english_name": "Moss Coin"
  },
  {
    "market": "KRW-PEPE",
    "korean_name": "페페",
    "english_name": "PEPE"
  },
  {
    "market": "KRW-CYBER",
    "korean_name": "사이버",
    "english_name": "Cyber"
  },
  {
    "market": "KRW-ARKM",
    "korean_name": "아캄",
    "english_name": "Arkham"
  },
  {
    "market": "KRW-PYR",
    "korean_name": "불칸 포지드",
    "english_name": "Vulcan Forged"
  },
  {
    "market": "KRW-IOTX",
    "korean_name": "아이오텍스",
    "english_name": "IoTeX"
  },
  {
    "market": "KRW-HIGH",
    "korean_name": "하이스트리트",
    "english_name": "Highstreet"
  },
  {
    "market": "KRW-PENDLE",
    "korean_name": "펜들",
    "english_name": "Pendle"
  },
  {
    "market": "KRW-BICO",
    "korean_name": "바이코노미",
    "english_name": "Biconomy"
  },
  {
    "market": "KRW-STORJ",
    "korean_name": "스토리지",
    "english_name": "Storj"
  },
  {
    "market": "KRW-API3",
    "korean_name": "에이피아이쓰리",
    "english_name": "API3"
  },
  {
    "market": "KRW-ZTX",
    "korean_name": "지티엑스",
    "english_name": "ZTX"
  },
  {
    "market": "KRW-MNT",
    "korean_name": "맨틀",
    "english_name": "Mantle"
  },
  {
    "market": "KRW-GTC",
    "korean_name": "깃코인",
    "english_name": "Gitcoin"
  },
  {
    "market": "KRW-METIS",
    "korean_name": "메티스다오",
    "english_name": "MetisDAO"
  },
  {
    "market": "KRW-TIA",
    "korean_name": "셀레스티아",
    "english_name": "Celestia"
  },
  {
    "market": "KRW-ICP",
    "korean_name": "인터넷 컴퓨터",
    "english_name": "Internet Computer"
  },
  {
    "market": "KRW-SPURS",
    "korean_name": "토트넘 홋스퍼",
    "english_name": "Tottenham Hotspur Fan Token"
  },
  {
    "market": "KRW-NEO",
    "korean_name": "네오",
    "english_name": "Neo"
  },
  {
    "market": "KRW-GAS",
    "korean_name": "가스",
    "english_name": "Gas"
  },
  {
    "market": "KRW-BIGTIME",
    "korean_name": "빅타임",
    "english_name": "Big Time"
  },
  {
    "market": "KRW-ZETA",
    "korean_name": "제타체인",
    "english_name": "ZetaChain"
  },
  {
    "market": "KRW-GRS",
    "korean_name": "그로스톨코인",
    "english_name": "Groestlcoin"
  },
  {
    "market": "KRW-ARK",
    "korean_name": "아크",
    "english_name": "Ark"
  },
  {
    "market": "KRW-YGG",
    "korean_name": "일드길드게임즈",
    "english_name": "Yield Guild Games"
  },
  {
    "market": "KRW-HUNT",
    "korean_name": "헌트",
    "english_name": "Hunt Town"
  },
  {
    "market": "KRW-KAVA",
    "korean_name": "카바",
    "english_name": "Kava"
  },
  {
    "market": "KRW-MAGIC",
    "korean_name": "매직",
    "english_name": "Magic"
  },
  {
    "market": "KRW-AUCTION",
    "korean_name": "바운스토큰",
    "english_name": "Bounce Token"
  },
  {
    "market": "KRW-USDT",
    "korean_name": "테더",
    "english_name": "Tether USDt"
  },
  {
    "market": "KRW-USDC",
    "korean_name": "유에스디코인",
    "english_name": "USD Coin"
  },
  {
    "market": "KRW-RAD",
    "korean_name": "래드웍스",
    "english_name": "Radworks"
  },
  {
    "market": "KRW-LSK",
    "korean_name": "리스크",
    "english_name": "Lisk"
  },
  {
    "market": "KRW-TT",
    "korean_name": "썬더코어",
    "english_name": "ThunderCore"
  },
  {
    "market": "KRW-ACE",
    "korean_name": "퓨저니스트",
    "english_name": "Fusionist"
  },
  {
    "market": "KRW-SKL",
    "korean_name": "스케일",
    "english_name": "SKALE"
  },
  {
    "market": "KRW-IQ",
    "korean_name": "아이큐",
    "english_name": "IQ"
  },
  {
    "market": "KRW-PYTH",
    "korean_name": "피스 네트워크",
    "english_name": "Pyth Network"
  },
  {
    "market": "KRW-MANTA",
    "korean_name": "만타 네트워크",
    "english_name": "Manta Network"
  },
  {
    "market": "KRW-AKT",
    "korean_name": "아카시 네트워크",
    "english_name": "Akash Network"
  },
  {
    "market": "KRW-BEAM",
    "korean_name": "빔",
    "english_name": "Beam"
  },
  {
    "market": "KRW-JTO",
    "korean_name": "지토",
    "english_name": "Jito"
  },
  {
    "market": "KRW-JUP",
    "korean_name": "주피터",
    "english_name": "Jupiter"
  },
  {
    "market": "KRW-STRK",
    "korean_name": "스타크넷",
    "english_name": "Starknet"
  },
  {
    "market": "KRW-SC",
    "korean_name": "시아코인",
    "english_name": "Siacoin"
  },
  {
    "market": "KRW-BONK",
    "korean_name": "봉크",
    "english_name": "Bonk"
  },
  {
    "market": "KRW-TOKAMAK",
    "korean_name": "토카막 네트워크",
    "english_name": "Tokamak Network"
  },
  {
    "market": "KRW-AIOZ",
    "korean_name": "아이오즈 네트워크",
    "english_name": "AIOZ Network"
  },
  {
    "market": "KRW-ZK",
    "korean_name": "지케이싱크",
    "english_name": "zkSync"
  },
  {
    "market": "KRW-ONDO",
    "korean_name": "온도 파이낸스",
    "english_name": "Ondo Finance"
  },
  {
    "market": "KRW-ALT",
    "korean_name": "알트레이어",
    "english_name": "AltLayer"
  },
  {
    "market": "KRW-NEAR",
    "korean_name": "니어프로토콜",
    "english_name": "NEAR Protocol"
  },
  {
    "market": "KRW-RON",
    "korean_name": "로닌",
    "english_name": "Ronin"
  },
  {
    "market": "KRW-FIDA",
    "korean_name": "솔라나 네임 서비스",
    "english_name": "Solana Name Service"
  },
  {
    "market": "KRW-STRAX",
    "korean_name": "스트라티스",
    "english_name": "Stratis"
  },
  {
    "market": "KRW-XAI",
    "korean_name": "자이",
    "english_name": "Xai"
  },
  {
    "market": "KRW-W",
    "korean_name": "웜홀",
    "english_name": "Wormhole"
  },
  {
    "market": "KRW-POLYX",
    "korean_name": "폴리매쉬",
    "english_name": "Polymesh"
  },
  {
    "market": "KRW-CORE",
    "korean_name": "코어",
    "english_name": "Core"
  },
  {
    "market": "KRW-BB",
    "korean_name": "바운스빗",
    "english_name": "BounceBit"
  },
  {
    "market": "KRW-POKT",
    "korean_name": "포켓네트워크",
    "english_name": "Pocket Network"
  },
  {
    "market": "KRW-REZ",
    "korean_name": "렌조",
    "english_name": "Renzo"
  },
  {
    "market": "KRW-OMNI",
    "korean_name": "옴니 네트워크",
    "english_name": "Omni Network"
  },
  {
    "market": "KRW-ENA",
    "korean_name": "에테나",
    "english_name": "Ethena"
  },
  {
    "market": "KRW-MOCA",
    "korean_name": "모카네트워크",
    "english_name": "Moca Network"
  },
  {
    "market": "KRW-ETHFI",
    "korean_name": "이더파이",
    "english_name": "ether.fi"
  },
  {
    "market": "KRW-MEW",
    "korean_name": "캣인어독스월드",
    "english_name": "cat in a dogs world"
  },
  {
    "market": "KRW-ZRO",
    "korean_name": "레이어제로",
    "english_name": "LayerZero"
  },
  {
    "market": "KRW-IO",
    "korean_name": "아이오넷",
    "english_name": "io.net"
  },
  {
    "market": "KRW-BLAST",
    "korean_name": "블라스트",
    "english_name": "Blast"
  },
  {
    "market": "KRW-TAIKO",
    "korean_name": "타이코",
    "english_name": "Taiko"
  },
  {
    "market": "KRW-BRETT",
    "korean_name": "브렛",
    "english_name": "Brett"
  },
  {
    "market": "KRW-ATH",
    "korean_name": "에이셔",
    "english_name": "Aethir"
  },
  {
    "market": "KRW-PCI",
    "korean_name": "페이코인",
    "english_name": "Paycoin"
  },
  {
    "market": "KRW-AVAIL",
    "korean_name": "어베일",
    "english_name": "Avail"
  },
  {
    "market": "KRW-TON",
    "korean_name": "톤코인",
    "english_name": "Toncoin"
  },
  {
    "market": "KRW-G",
    "korean_name": "그래비티",
    "english_name": "Gravity"
  },
  {
    "market": "KRW-LISTA",
    "korean_name": "리스타 다오",
    "english_name": "Lista DAO"
  },
  {
    "market": "KRW-PEAQ",
    "korean_name": "피크",
    "english_name": "peaq"
  },
  {
    "market": "KRW-EIGEN",
    "korean_name": "아이겐레이어",
    "english_name": "EigenLayer"
  },
  {
    "market": "KRW-ORDER",
    "korean_name": "오덜리 네트워크",
    "english_name": "Orderly Network"
  },
  {
    "market": "KRW-MERL",
    "korean_name": "멀린 체인",
    "english_name": "Merlin Chain"
  },
  {
    "market": "KRW-SCR",
    "korean_name": "스크롤",
    "english_name": "Scroll"
  },
  {
    "market": "KRW-SWELL",
    "korean_name": "스웰 네트워크",
    "english_name": "Swell Network"
  },
  {
    "market": "KRW-UXLINK",
    "korean_name": "유엑스링크",
    "english_name": "UXLINK"
  },
  {
    "market": "KRW-SKY",
    "korean_name": "스카이 프로토콜",
    "english_name": "Sky Protocol"
  },
  {
    "market": "KRW-PONKE",
    "korean_name": "폰케",
    "english_name": "Ponke"
  },
  {
    "market": "KRW-MVL",
    "korean_name": "엠블",
    "english_name": "MVL"
  },
  {
    "market": "KRW-CARV",
    "korean_name": "카브",
    "english_name": "CARV"
  },
  {
    "market": "KRW-PUFFER",
    "korean_name": "퍼퍼",
    "english_name": "Puffer"
  },
  {
    "market": "KRW-SUNDOG",
    "korean_name": "썬도그",
    "english_name": "Sundog"
  },
  {
    "market": "KRW-TURBO",
    "korean_name": "터보",
    "english_name": "Turbo"
  },
  {
    "market": "KRW-RAY",
    "korean_name": "레이디움",
    "english_name": "Raydium"
  },
  {
    "market": "KRW-SAFE",
    "korean_name": "세이프",
    "english_name": "Safe"
  },
  {
    "market": "KRW-VIRTUAL",
    "korean_name": "버추얼 프로토콜",
    "english_name": "Virtuals Protocol"
  },
  {
    "market": "KRW-DRIFT",
    "korean_name": "드리프트",
    "english_name": "Drift"
  },
  {
    "market": "KRW-MOVE",
    "korean_name": "무브먼트",
    "english_name": "Movement"
  },
  {
    "market": "KRW-F",
    "korean_name": "신퓨처스",
    "english_name": "Synfutures"
  },
  {
    "market": "KRW-DEEP",
    "korean_name": "딥북",
    "english_name": "DeepBook"
  },
  {
    "market": "KRW-MORPHO",
    "korean_name": "모포",
    "english_name": "Morpho"
  },
  {
    "market": "KRW-NEIRO",
    "korean_name": "네이로",
    "english_name": "Neiro"
  },
  {
    "market": "KRW-MOODENG",
    "korean_name": "무뎅",
    "english_name": "Moo Deng"
  },
  {
    "market": "KRW-DBR",
    "korean_name": "디브릿지",
    "english_name": "deBridge"
  },
  {
    "market": "KRW-GOAT",
    "korean_name": "고트세우스 막시무스",
    "english_name": "Goatseus Maximus"
  },
  {
    "market": "KRW-NIL",
    "korean_name": "닐리온",
    "english_name": "Nillion"
  },
  {
    "market": "KRW-ME",
    "korean_name": "매직 에덴",
    "english_name": "Magic Eden"
  },
  {
    "market": "KRW-INIT",
    "korean_name": "이니시아",
    "english_name": "Initia"
  },
  {
    "market": "KRW-ZRC",
    "korean_name": "저킷",
    "english_name": "Zircuit"
  },
  {
    "market": "KRW-IOTA",
    "korean_name": "아이오타",
    "english_name": "IOTA"
  },
  {
    "market": "KRW-PENGU",
    "korean_name": "펏지 펭귄",
    "english_name": "Pudgy Penguins"
  },
  {
    "market": "KRW-ACX",
    "korean_name": "어크로스 프로토콜",
    "english_name": "Across Protocol"
  },
  {
    "market": "KRW-AERO",
    "korean_name": "에어로드롬 파이낸스",
    "english_name": "Aerodrome Finance"
  },
  {
    "market": "KRW-THE",
    "korean_name": "테나",
    "english_name": "THENA"
  },
  {
    "market": "KRW-AMP",
    "korean_name": "앰프",
    "english_name": "Amp"
  },
  {
    "market": "KRW-VANA",
    "korean_name": "바나",
    "english_name": "Vana"
  },
  {
    "market": "KRW-XYO",
    "korean_name": "엑스와이오",
    "english_name": "XYO"
  },
  {
    "market": "KRW-A8",
    "korean_name": "에인션트8",
    "english_name": "Ancient8"
  },
  {
    "market": "KRW-SONIC",
    "korean_name": "소닉 에스브이엠",
    "english_name": "Sonic SVM"
  },
  {
    "market": "KRW-WIF",
    "korean_name": "도그위프햇",
    "english_name": "dogwifhat"
  },
  {
    "market": "KRW-IP",
    "korean_name": "스토리",
    "english_name": "Story"
  },
  {
    "market": "KRW-DKA",
    "korean_name": "디카르고",
    "english_name": "dKargo"
  },
  {
    "market": "KRW-SOLV",
    "korean_name": "솔브 프로토콜",
    "english_name": "Solv Protocol"
  },
  {
    "market": "KRW-BLUE",
    "korean_name": "블루핀",
    "english_name": "Bluefin"
  },
  {
    "market": "KRW-QKC",
    "korean_name": "쿼크체인",
    "english_name": "QuarkChain"
  },
  {
    "market": "KRW-HP",
    "korean_name": "히포 프로토콜",
    "english_name": "Hippo Protocol"
  },
  {
    "market": "KRW-GAME2",
    "korean_name": "게임빌드",
    "english_name": "GameBuild"
  },
  {
    "market": "KRW-ERA",
    "korean_name": "칼데라",
    "english_name": "Caldera"
  },
  {
    "market": "KRW-ARDR",
    "korean_name": "아더",
    "english_name": "Ardor"
  },
  {
    "market": "KRW-BOUNTY",
    "korean_name": "체인바운티",
    "english_name": "Chainbounty"
  },
  {
    "market": "KRW-SHELL",
    "korean_name": "마이쉘",
    "english_name": "MyShell"
  },
  {
    "market": "KRW-BERA",
    "korean_name": "베라체인",
    "english_name": "Berachain"
  },
  {
    "market": "KRW-BIO",
    "korean_name": "바이오 프로토콜",
    "english_name": "Bio Protocol"
  },
  {
    "market": "KRW-PLUME",
    "korean_name": "플룸",
    "english_name": "Plume"
  },
  {
    "market": "KRW-OBT",
    "korean_name": "오비터 파이낸스",
    "english_name": "Orbiter Finance"
  },
  {
    "market": "KRW-TRUMP",
    "korean_name": "오피셜 트럼프",
    "english_name": "OFFICIAL TRUMP"
  },
  {
    "market": "KRW-KERNEL",
    "korean_name": "커널 다오",
    "english_name": "Kernel DAO"
  },
  {
    "market": "KRW-COOKIE",
    "korean_name": "쿠키 다오",
    "english_name": "Cookie DAO"
  },
  {
    "market": "KRW-GNO",
    "korean_name": "노시스",
    "english_name": "Gnosis"
  },
  {
    "market": "KRW-VTHO",
    "korean_name": "비토르 토큰",
    "english_name": "VeThor Token"
  },
  {
    "market": "KRW-ANIME",
    "korean_name": "애니메코인",
    "english_name": "Animecoin"
  },
  {
    "market": "KRW-RED",
    "korean_name": "레드스톤",
    "english_name": "RedStone"
  },
  {
    "market": "KRW-LAYER",
    "korean_name": "솔레이어",
    "english_name": "Solayer"
  },
  {
    "market": "KRW-WCT",
    "korean_name": "월렛커넥트",
    "english_name": "WalletConnect"
  },
  {
    "market": "KRW-FLOCK",
    "korean_name": "플록",
    "english_name": "FLock.io"
  },
  {
    "market": "KRW-KAITO",
    "korean_name": "카이토",
    "english_name": "Kaito"
  },
  {
    "market": "KRW-BMT",
    "korean_name": "버블맵스",
    "english_name": "Bubblemaps"
  },
  {
    "market": "KRW-C",
    "korean_name": "체인베이스 토큰",
    "english_name": "Chainbase Token"
  },
  {
    "market": "KRW-SOON",
    "korean_name": "쑨",
    "english_name": "SOON"
  },
  {
    "market": "KRW-PAXG",
    "korean_name": "팍스골드",
    "english_name": "PAX Gold"
  },
  {
    "market": "KRW-AVL",
    "korean_name": "아발론",
    "english_name": "Avalon"
  },
  {
    "market": "KRW-B3",
    "korean_name": "비쓰리",
    "english_name": "B3"
  },
  {
    "market": "KRW-PUNDIAI",
    "korean_name": "펀디에이아이",
    "english_name": "Pundi AI"
  },
  {
    "market": "KRW-ELX",
    "korean_name": "엘릭서",
    "english_name": "Elixir"
  },
  {
    "market": "KRW-COW",
    "korean_name": "카우 프로토콜",
    "english_name": "CoW Protocol"
  },
  {
    "market": "KRW-WAL",
    "korean_name": "월러스",
    "english_name": "Walrus"
  },
  {
    "market": "KRW-BABY",
    "korean_name": "바빌론",
    "english_name": "Babylon"
  },
  {
    "market": "KRW-ES",
    "korean_name": "이클립스",
    "english_name": "Eclipse"
  },
  {
    "market": "KRW-XTER",
    "korean_name": "엑스테리오",
    "english_name": "Xterio"
  },
  {
    "market": "KRW-NXPC",
    "korean_name": "넥스페이스",
    "english_name": "NEXPACE"
  },
  {
    "market": "KRW-GRASS",
    "korean_name": "그래스",
    "english_name": "Grass"
  },
  {
    "market": "KRW-ORCA",
    "korean_name": "오르카",
    "english_name": "Orca"
  },
  {
    "market": "KRW-PUMP",
    "korean_name": "펌프",
    "english_name": "PUMP"
  },
  {
    "market": "KRW-EPT",
    "korean_name": "밸런스",
    "english_name": "Balance"
  },
  {
    "market": "KRW-HAEDAL",
    "korean_name": "해달 프로토콜",
    "english_name": "Haedal Protocol"
  },
  {
    "market": "KRW-AI16Z",
    "korean_name": "에이아이식스틴즈",
    "english_name": "ai16z"
  },
  {
    "market": "KRW-PARTI",
    "korean_name": "파티클 네트워크",
    "english_name": "Particle Network"
  },
  {
    "market": "KRW-SXT",
    "korean_name": "스페이스 앤드 타임",
    "english_name": "Space and Time"
  },
  {
    "market": "KRW-PROMPT",
    "korean_name": "웨이파인더",
    "english_name": "Wayfinder"
  },
  {
    "market": "KRW-SIGN",
    "korean_name": "사인",
    "english_name": "Sign"
  },
  {
    "market": "KRW-SAHARA",
    "korean_name": "사하라에이아이",
    "english_name": "Sahara AI"
  },
  {
    "market": "KRW-H",
    "korean_name": "휴머니티 프로토콜",
    "english_name": "Humanity Protocol"
  },
  {
    "market": "KRW-HOME",
    "korean_name": "디파이 앱",
    "english_name": "Defi App"
  },
  {
    "market": "KRW-OM",
    "korean_name": "만트라",
    "english_name": "MANTRA"
  },
  {
    "market": "KRW-LA",
    "korean_name": "라그랑주",
    "english_name": "Lagrange"
  },
  {
    "market": "KRW-SOPH",
    "korean_name": "소폰",
    "english_name": "Sophon"
  },
  {
    "market": "KRW-HYPER",
    "korean_name": "하이퍼레인",
    "english_name": "Hyperlane"
  },
  {
    "market": "KRW-PROVE",
    "korean_name": "석싱트",
    "english_name": "Succinct"
  },
  {
    "market": "KRW-FORT",
    "korean_name": "포르타",
    "english_name": "Forta"
  },
  {
    "market": "KRW-HUMA",
    "korean_name": "후마 파이낸스",
    "english_name": "Huma Finance"
  },
  {
    "market": "KRW-SPK",
    "korean_name": "스파크",
    "english_name": "Spark"
  },
  {
    "market": "KRW-SYRUP",
    "korean_name": "메이플 파이낸스",
    "english_name": "Maple Finance"
  },
  {
    "market": "KRW-NEWT",
    "korean_name": "뉴턴 프로토콜",
    "english_name": "Newton Protocol"
  },
  {
    "market": "KRW-RESOLV",
    "korean_name": "리졸브",
    "english_name": "Resolv"
  },
  {
    "market": "KRW-TREE",
    "korean_name": "트리하우스",
    "english_name": "Treehouse"
  },
  {
    "market": "KRW-TOWNS",
    "korean_name": "타운즈",
    "english_name": "Towns"
  },
  {
    "market": "BTC-ETH",
    "korean_name": "이더리움",
    "english_name": "Ethereum"
  },
  {
    "market": "BTC-XRP",
    "korean_name": "엑스알피 [리플]",
    "english_name": "XRP"
  },
  {
    "market": "BTC-KAIA",
    "korean_name": "카이아",
    "english_name": "Kaia"
  },
  {
    "market": "BTC-KSP",
    "korean_name": "클레이스왑",
    "english_name": "KlaySwap Protocol"
  },
  {
    "market": "BTC-DOGE",
    "korean_name": "도지코인",
    "english_name": "Dogecoin"
  },
  {
    "market": "BTC-BNB",
    "korean_name": "비앤비",
    "english_name": "BNB"
  },
  {
    "market": "BTC-SOL",
    "korean_name": "솔라나",
    "english_name": "Solana"
  },
  {
    "market": "BTC-ENS",
    "korean_name": "이더리움네임서비스",
    "english_name": "Ethereum Name Service"
  },
  {
    "market": "BTC-CSPR",
    "korean_name": "캐스퍼",
    "english_name": "Casper"
  },
  {
    "market": "BTC-WITCH",
    "korean_name": "위치 토큰",
    "english_name": "Witch Token"
  },
  {
    "market": "BTC-TALK",
    "korean_name": "톡큰",
    "english_name": "Talken"
  },
  {
    "market": "BTC-DICE",
    "korean_name": "클레이다이스",
    "english_name": "KLAYDICE"
  },
  {
    "market": "BTC-AHT",
    "korean_name": "아하토큰",
    "english_name": "AhaToken"
  },
  {
    "market": "BTC-HVH",
    "korean_name": "하바",
    "english_name": "HAVAH"
  },
  {
    "market": "USDT-AMP",
    "korean_name": "앰프",
    "english_name": "Amp"
  }
]
```

---

## get_ticker

**설명**: 현재가 조회 - BTC의 실시간 거래 정보

**함수 호출**: `get_ticker(market)`

**입력 파라미터**:
```json
{
  "market": "KRW-BTC"
}
```

**응답 타입**: list

**응답 길이**: 779 문자

**캡처 시간**: 2025-08-26T00:27:13.173914

**응답 데이터**:
```json
[
  {
    "market": "KRW-BTC",
    "trade_date": "20250825",
    "trade_time": "152707",
    "trade_date_kst": "20250826",
    "trade_time_kst": "002707",
    "trade_timestamp": 1756168027954,
    "opening_price": 157120000,
    "high_price": 157476000,
    "low_price": 156602000,
    "trade_price": 157450000,
    "prev_closing_price": 157120000,
    "change": "RISE",
    "change_price": 330000,
    "change_rate": 0.0021,
    "signed_change_price": 330000,
    "signed_change_rate": 0.0021,
    "trade_volume": 0.00040361,
    "acc_trade_price": 2675920640.37342,
    "acc_trade_price_24h": 205839989370.0371,
    "acc_trade_volume": 17.03631171,
    "acc_trade_volume_24h": 1311.88031357,
    "highest_52_week_price": 169900000,
    "highest_52_week_date": "2025-08-15",
    "lowest_52_week_price": 72029000,
    "lowest_52_week_date": "2024-09-08",
    "timestamp": 1756135632646
  }
]
```

---

## get_orderbook

**설명**: 호가 정보 조회 - BTC의 매수/매도 호가 정보

**함수 호출**: `get_orderbook(market)`

**입력 파라미터**:
```json
{
  "market": "KRW-BTC"
}
```

**응답 타입**: list

**응답 길이**: 2812 문자

**캡처 시간**: 2025-08-26T00:27:13.219854

**응답 데이터**:
```json
[
  {
    "market": "KRW-BTC",
    "timestamp": 1756135632391949,
    "total_ask_size": 4724587000,
    "total_bid_size": 0.4241,
    "orderbook_units": [
      {
        "ask_price": 157450000,
        "bid_price": 157408000,
        "ask_size": 0.0019,
        "bid_size": 0.0001
      },
      {
        "ask_price": 157451000,
        "bid_price": 157400000,
        "ask_size": 0.2987,
        "bid_size": 0.0344
      },
      {
        "ask_price": 157454000,
        "bid_price": 157394000,
        "ask_size": 0,
        "bid_size": 0.0192
      },
      {
        "ask_price": 157462000,
        "bid_price": 157392000,
        "ask_size": 0.0045,
        "bid_size": 0.0006
      },
      {
        "ask_price": 157476000,
        "bid_price": 157375000,
        "ask_size": 0.0035,
        "bid_size": 0.0009
      },
      {
        "ask_price": 157477000,
        "bid_price": 157368000,
        "ask_size": 0.0001,
        "bid_size": 0.002
      },
      {
        "ask_price": 157478000,
        "bid_price": 157357000,
        "ask_size": 0.0019,
        "bid_size": 0.0002
      },
      {
        "ask_price": 157480000,
        "bid_price": 157353000,
        "ask_size": 0,
        "bid_size": 0.0581
      },
      {
        "ask_price": 157481000,
        "bid_price": 157352000,
        "ask_size": 0.2354,
        "bid_size": 0.0038
      },
      {
        "ask_price": 157482000,
        "bid_price": 157344000,
        "ask_size": 0.2054,
        "bid_size": 0.0183
      },
      {
        "ask_price": 157483000,
        "bid_price": 157342000,
        "ask_size": 0.0143,
        "bid_size": 0.0063
      },
      {
        "ask_price": 157484000,
        "bid_price": 157339000,
        "ask_size": 0.0019,
        "bid_size": 0.001
      },
      {
        "ask_price": 157485000,
        "bid_price": 157334000,
        "ask_size": 0.0001,
        "bid_size": 0.0031
      },
      {
        "ask_price": 157486000,
        "bid_price": 157327000,
        "ask_size": 0.0038,
        "bid_size": 0.0025
      },
      {
        "ask_price": 157488000,
        "bid_price": 157321000,
        "ask_size": 0.0001,
        "bid_size": 0.0654
      },
      {
        "ask_price": 157489000,
        "bid_price": 157320000,
        "ask_size": 0.001,
        "bid_size": 0.0063
      },
      {
        "ask_price": 157490000,
        "bid_price": 157315000,
        "ask_size": 0,
        "bid_size": 0.0001
      },
      {
        "ask_price": 157491000,
        "bid_price": 157300000,
        "ask_size": 0.0001,
        "bid_size": 0.0031
      },
      {
        "ask_price": 157493000,
        "bid_price": 157295000,
        "ask_size": 0.0001,
        "bid_size": 0.0128
      },
      {
        "ask_price": 157494000,
        "bid_price": 157294000,
        "ask_size": 0.0012,
        "bid_size": 0.0014
      },
      {
        "ask_price": 157495000,
        "bid_price": 157288000,
        "ask_size": 0.9221,
        "bid_size": 0.0227
      },
      {
        "ask_price": 157498000,
        "bid_price": 157281000,
        "ask_size": 0.0275,
        "bid_size": 0.0045
      },
      {
        "ask_price": 157499000,
        "bid_price": 157280000,
        "ask_size": 0.0077,
        "bid_size": 0.0003
      },
      {
        "ask_price": 157500000,
        "bid_price": 157273000,
        "ask_size": 0.5046,
        "bid_size": 0.0001
      },
      {
        "ask_price": 157501000,
        "bid_price": 157271000,
        "ask_size": 0.0013,
        "bid_size": 0.006
      },
      {
        "ask_price": 157502000,
        "bid_price": 157270000,
        "ask_size": 0.0001,
        "bid_size": 0.0006
      },
      {
        "ask_price": 157503000,
        "bid_price": 157258000,
        "ask_size": 0.0008,
        "bid_size": 0.1489
      },
      {
        "ask_price": 157504000,
        "bid_price": 157255000,
        "ask_size": 0.0269,
        "bid_size": 0.0001
      },
      {
        "ask_price": 157505000,
        "bid_price": 157250000,
        "ask_size": 0.0004,
        "bid_size": 0.0012
      },
      {
        "ask_price": 157506000,
        "bid_price": 157247000,
        "ask_size": 0.0013,
        "bid_size": 0.0001
      }
    ]
  }
]
```

---

## get_candles

**설명**: 캔들 데이터 조회 - BTC의 1분봉 5개 데이터

**함수 호출**: `get_candles(market, unit, count)`

**입력 파라미터**:
```json
{
  "market": "KRW-BTC",
  "unit": "days",
  "count": 5
}
```

**응답 타입**: list

**응답 길이**: 1701 문자

**캡처 시간**: 2025-08-26T00:27:13.252591

**응답 데이터**:
```json
[
  {
    "market": "KRW-BTC",
    "candle_date_time_utc": "2025-08-25T15:27:00",
    "candle_date_time_kst": "2025-08-26T00:27:00",
    "opening_price": 157446000,
    "high_price": 157451000,
    "low_price": 157408000,
    "trade_price": 157450000,
    "timestamp": 1756135628000,
    "candle_acc_trade_price": 18687538.34284,
    "candle_acc_trade_volume": 0.11868932,
    "unit": 1
  },
  {
    "market": "KRW-BTC",
    "candle_date_time_utc": "2025-08-25T15:26:00",
    "candle_date_time_kst": "2025-08-26T00:26:00",
    "opening_price": 157408000,
    "high_price": 157476000,
    "low_price": 157408000,
    "trade_price": 157446000,
    "timestamp": 1756135619946,
    "candle_acc_trade_price": 138874026.10666,
    "candle_acc_trade_volume": 0.88206496,
    "unit": 1
  },
  {
    "market": "KRW-BTC",
    "candle_date_time_utc": "2025-08-25T15:25:00",
    "candle_date_time_kst": "2025-08-26T00:25:00",
    "opening_price": 157241000,
    "high_price": 157408000,
    "low_price": 157241000,
    "trade_price": 157408000,
    "timestamp": 1756135559302,
    "candle_acc_trade_price": 227818779.9846,
    "candle_acc_trade_volume": 1.44806873,
    "unit": 1
  },
  {
    "market": "KRW-BTC",
    "candle_date_time_utc": "2025-08-25T15:24:00",
    "candle_date_time_kst": "2025-08-26T00:24:00",
    "opening_price": 157220000,
    "high_price": 157241000,
    "low_price": 157203000,
    "trade_price": 157241000,
    "timestamp": 1756135499195,
    "candle_acc_trade_price": 53912913.55096,
    "candle_acc_trade_volume": 0.34291792,
    "unit": 1
  },
  {
    "market": "KRW-BTC",
    "candle_date_time_utc": "2025-08-25T15:23:00",
    "candle_date_time_kst": "2025-08-26T00:23:00",
    "opening_price": 157241000,
    "high_price": 157242000,
    "low_price": 157219000,
    "trade_price": 157220000,
    "timestamp": 1756135437348,
    "candle_acc_trade_price": 58776458.55759,
    "candle_acc_trade_volume": 0.37383875,
    "unit": 1
  }
]
```

---

## get_daily_candles

**설명**: 일봉 데이터 조회 - BTC의 30일 일봉 데이터

**함수 호출**: `get_daily_candles(market, count)`

**입력 파라미터**:
```json
{
  "market": "KRW-BTC",
  "count": 30
}
```

**응답 타입**: list

**응답 길이**: 13578 문자

**캡처 시간**: 2025-08-26T00:27:13.284719

**응답 데이터**:
```json
[
  {
    "market": "KRW-BTC",
    "candle_date_time_utc": "2025-08-25T15:00:00",
    "candle_date_time_kst": "2025-08-26T00:00:00",
    "opening_price": 157120000,
    "high_price": 157476000,
    "low_price": 156602000,
    "trade_price": 157450000,
    "timestamp": 1756135628000,
    "candle_acc_trade_price": 2675920640.37342,
    "candle_acc_trade_volume": 17.03631171,
    "prev_closing_price": 157120000,
    "change_price": 330000,
    "change_rate": 0.0021003055,
    "converted_trade_price": null
  },
  {
    "market": "KRW-BTC",
    "candle_date_time_utc": "2025-08-24T15:00:00",
    "candle_date_time_kst": "2025-08-25T00:00:00",
    "opening_price": 159190000,
    "high_price": 159496000,
    "low_price": 155300000,
    "trade_price": 157120000,
    "timestamp": 1756133997447,
    "candle_acc_trade_price": 205095147921.70865,
    "candle_acc_trade_volume": 1306.96991129,
    "prev_closing_price": 159197000,
    "change_price": -2077000,
    "change_rate": -0.0130467283,
    "converted_trade_price": null
  },
  {
    "market": "KRW-BTC",
    "candle_date_time_utc": "2025-08-23T15:00:00",
    "candle_date_time_kst": "2025-08-24T00:00:00",
    "opening_price": 159000000,
    "high_price": 160230000,
    "low_price": 158946000,
    "trade_price": 159197000,
    "timestamp": 1756047597444,
    "candle_acc_trade_price": 59158237460.00226,
    "candle_acc_trade_volume": 370.81727868,
    "prev_closing_price": 159001000,
    "change_price": 196000,
    "change_rate": 0.0012326966,
    "converted_trade_price": null
  },
  {
    "market": "KRW-BTC",
    "candle_date_time_utc": "2025-08-22T15:00:00",
    "candle_date_time_kst": "2025-08-23T00:00:00",
    "opening_price": 161183000,
    "high_price": 162691000,
    "low_price": 158999000,
    "trade_price": 159001000,
    "timestamp": 1755961197590,
    "candle_acc_trade_price": 142931253912.81406,
    "candle_acc_trade_volume": 889.03529787,
    "prev_closing_price": 161183000,
    "change_price": -2182000,
    "change_rate": -0.0135374078,
    "converted_trade_price": null
  },
  {
    "market": "KRW-BTC",
    "candle_date_time_utc": "2025-08-21T15:00:00",
    "candle_date_time_kst": "2025-08-22T00:00:00",
    "opening_price": 158476000,
    "high_price": 161902000,
    "low_price": 156710000,
    "trade_price": 161183000,
    "timestamp": 1755874799276,
    "candle_acc_trade_price": 151407193720.72244,
    "candle_acc_trade_volume": 951.08764432,
    "prev_closing_price": 158476000,
    "change_price": 2707000,
    "change_rate": 0.0170814508,
    "converted_trade_price": null
  },
  {
    "market": "KRW-BTC",
    "candle_date_time_utc": "2025-08-20T15:00:00",
    "candle_date_time_kst": "2025-08-21T00:00:00",
    "opening_price": 158473000,
    "high_price": 160000000,
    "low_price": 157927000,
    "trade_price": 158476000,
    "timestamp": 1755788397725,
    "candle_acc_trade_price": 80679197893.58871,
    "candle_acc_trade_volume": 507.86922514,
    "prev_closing_price": 158473000,
    "change_price": 3000,
    "change_rate": 1.89307e-05,
    "converted_trade_price": null
  },
  {
    "market": "KRW-BTC",
    "candle_date_time_utc": "2025-08-19T15:00:00",
    "candle_date_time_kst": "2025-08-20T00:00:00",
    "opening_price": 159000000,
    "high_price": 159400000,
    "low_price": 156898000,
    "trade_price": 158473000,
    "timestamp": 1755701998810,
    "candle_acc_trade_price": 133343333649.68823,
    "candle_acc_trade_volume": 841.80182295,
    "prev_closing_price": 159000000,
    "change_price": -527000,
    "change_rate": -0.0033144654,
    "converted_trade_price": null
  },
  {
    "market": "KRW-BTC",
    "candle_date_time_utc": "2025-08-18T15:00:00",
    "candle_date_time_kst": "2025-08-19T00:00:00",
    "opening_price": 160889000,
    "high_price": 162497000,
    "low_price": 158885000,
    "trade_price": 159000000,
    "timestamp": 1755615599801,
    "candle_acc_trade_price": 99386909316.81592,
    "candle_acc_trade_volume": 618.66937292,
    "prev_closing_price": 160896000,
    "change_price": -1896000,
    "change_rate": -0.0117840095,
    "converted_trade_price": null
  },
  {
    "market": "KRW-BTC",
    "candle_date_time_utc": "2025-08-17T15:00:00",
    "candle_date_time_kst": "2025-08-18T00:00:00",
    "opening_price": 163501000,
    "high_price": 163709000,
    "low_price": 159890000,
    "trade_price": 160896000,
    "timestamp": 1755529197532,
    "candle_acc_trade_price": 132458514711.55746,
    "candle_acc_trade_volume": 821.08421999,
    "prev_closing_price": 163501000,
    "change_price": -2605000,
    "change_rate": -0.0159326243,
    "converted_trade_price": null
  },
  {
    "market": "KRW-BTC",
    "candle_date_time_utc": "2025-08-16T15:00:00",
    "candle_date_time_kst": "2025-08-17T00:00:00",
    "opening_price": 163286000,
    "high_price": 164109000,
    "low_price": 162931000,
    "trade_price": 163501000,
    "timestamp": 1755442799704,
    "candle_acc_trade_price": 41117636728.86388,
    "candle_acc_trade_volume": 251.36781373,
    "prev_closing_price": 163286000,
    "change_price": 215000,
    "change_rate": 0.0013167081,
    "converted_trade_price": null
  },
  {
    "market": "KRW-BTC",
    "candle_date_time_utc": "2025-08-15T15:00:00",
    "candle_date_time_kst": "2025-08-16T00:00:00",
    "opening_price": 163409000,
    "high_price": 164656000,
    "low_price": 162754000,
    "trade_price": 163286000,
    "timestamp": 1755356397517,
    "candle_acc_trade_price": 68014145251.41696,
    "candle_acc_trade_volume": 416.03609965,
    "prev_closing_price": 163409000,
    "change_price": -123000,
    "change_rate": -0.0007527125,
    "converted_trade_price": null
  },
  {
    "market": "KRW-BTC",
    "candle_date_time_utc": "2025-08-14T15:00:00",
    "candle_date_time_kst": "2025-08-15T00:00:00",
    "opening_price": 164397000,
    "high_price": 165785000,
    "low_price": 162897000,
    "trade_price": 163409000,
    "timestamp": 1755269998885,
    "candle_acc_trade_price": 109387620445.12003,
    "candle_acc_trade_volume": 665.23037935,
    "prev_closing_price": 164416000,
    "change_price": -1007000,
    "change_rate": -0.0061247081,
    "converted_trade_price": null
  },
  {
    "market": "KRW-BTC",
    "candle_date_time_utc": "2025-08-13T15:00:00",
    "candle_date_time_kst": "2025-08-14T00:00:00",
    "opening_price": 165135000,
    "high_price": 169900000,
    "low_price": 162392000,
    "trade_price": 164416000,
    "timestamp": 1755183599895,
    "candle_acc_trade_price": 288211636040.3942,
    "candle_acc_trade_volume": 1732.18580509,
    "prev_closing_price": 165167000,
    "change_price": -751000,
    "change_rate": -0.0045469131,
    "converted_trade_price": null
  },
  {
    "market": "KRW-BTC",
    "candle_date_time_utc": "2025-08-12T15:00:00",
    "candle_date_time_kst": "2025-08-13T00:00:00",
    "opening_price": 164380000,
    "high_price": 166500000,
    "low_price": 163378000,
    "trade_price": 165167000,
    "timestamp": 1755097198886,
    "candle_acc_trade_price": 153039454587.6141,
    "candle_acc_trade_volume": 930.31464209,
    "prev_closing_price": 164380000,
    "change_price": 787000,
    "change_rate": 0.0047876871,
    "converted_trade_price": null
  },
  {
    "market": "KRW-BTC",
    "candle_date_time_utc": "2025-08-11T15:00:00",
    "candle_date_time_kst": "2025-08-12T00:00:00",
    "opening_price": 165310000,
    "high_price": 165608000,
    "low_price": 163085000,
    "trade_price": 164380000,
    "timestamp": 1755010799739,
    "candle_acc_trade_price": 116539572819.6604,
    "candle_acc_trade_volume": 710.06527528,
    "prev_closing_price": 165310000,
    "change_price": -930000,
    "change_rate": -0.005625794,
    "converted_trade_price": null
  },
  {
    "market": "KRW-BTC",
    "candle_date_time_utc": "2025-08-10T15:00:00",
    "candle_date_time_kst": "2025-08-11T00:00:00",
    "opening_price": 162758000,
    "high_price": 167045000,
    "low_price": 162161000,
    "trade_price": 165310000,
    "timestamp": 1754924397544,
    "candle_acc_trade_price": 208196613392.82016,
    "candle_acc_trade_volume": 1259.77248262,
    "prev_closing_price": 162758000,
    "change_price": 2552000,
    "change_rate": 0.0156797208,
    "converted_trade_price": null
  },
  {
    "market": "KRW-BTC",
    "candle_date_time_utc": "2025-08-09T15:00:00",
    "candle_date_time_kst": "2025-08-10T00:00:00",
    "opening_price": 160650000,
    "high_price": 162900000,
    "low_price": 160000000,
    "trade_price": 162758000,
    "timestamp": 1754837997581,
    "candle_acc_trade_price": 120959523668.20789,
    "candle_acc_trade_volume": 748.18221097,
    "prev_closing_price": 160650000,
    "change_price": 2108000,
    "change_rate": 0.0131216931,
    "converted_trade_price": null
  },
  {
    "market": "KRW-BTC",
    "candle_date_time_utc": "2025-08-08T15:00:00",
    "candle_date_time_kst": "2025-08-09T00:00:00",
    "opening_price": 160530000,
    "high_price": 161561000,
    "low_price": 160000000,
    "trade_price": 160650000,
    "timestamp": 1754751597599,
    "candle_acc_trade_price": 84001910721.92195,
    "candle_acc_trade_volume": 523.21133384,
    "prev_closing_price": 160556000,
    "change_price": 94000,
    "change_rate": 0.0005854655,
    "converted_trade_price": null
  },
  {
    "market": "KRW-BTC",
    "candle_date_time_utc": "2025-08-07T15:00:00",
    "candle_date_time_kst": "2025-08-08T00:00:00",
    "opening_price": 161080000,
    "high_price": 162150000,
    "low_price": 160301000,
    "trade_price": 160556000,
    "timestamp": 1754665199269,
    "candle_acc_trade_price": 102366778716.13356,
    "candle_acc_trade_volume": 635.58094255,
    "prev_closing_price": 161078000,
    "change_price": -522000,
    "change_rate": -0.003240666,
    "converted_trade_price": null
  },
  {
    "market": "KRW-BTC",
    "candle_date_time_utc": "2025-08-06T15:00:00",
    "candle_date_time_kst": "2025-08-07T00:00:00",
    "opening_price": 160529000,
    "high_price": 161594000,
    "low_price": 159468000,
    "trade_price": 161078000,
    "timestamp": 1754578798893,
    "candle_acc_trade_price": 80726041742.82274,
    "candle_acc_trade_volume": 502.71307393,
    "prev_closing_price": 160529000,
    "change_price": 549000,
    "change_rate": 0.0034199428,
    "converted_trade_price": null
  },
  {
    "market": "KRW-BTC",
    "candle_date_time_utc": "2025-08-05T15:00:00",
    "candle_date_time_kst": "2025-08-06T00:00:00",
    "opening_price": 158502000,
    "high_price": 160550000,
    "low_price": 158085000,
    "trade_price": 160529000,
    "timestamp": 1754492399020,
    "candle_acc_trade_price": 68397971054.86367,
    "candle_acc_trade_volume": 429.20437705,
    "prev_closing_price": 158502000,
    "change_price": 2027000,
    "change_rate": 0.0127884822,
    "converted_trade_price": null
  },
  {
    "market": "KRW-BTC",
    "candle_date_time_utc": "2025-08-04T15:00:00",
    "candle_date_time_kst": "2025-08-05T00:00:00",
    "opening_price": 160013000,
    "high_price": 161000000,
    "low_price": 158000000,
    "trade_price": 158502000,
    "timestamp": 1754405997610,
    "candle_acc_trade_price": 78840578829.37044,
    "candle_acc_trade_volume": 493.38238358,
    "prev_closing_price": 160019000,
    "change_price": -1517000,
    "change_rate": -0.0094801242,
    "converted_trade_price": null
  },
  {
    "market": "KRW-BTC",
    "candle_date_time_utc": "2025-08-03T15:00:00",
    "candle_date_time_kst": "2025-08-04T00:00:00",
    "opening_price": 159350000,
    "high_price": 161280000,
    "low_price": 159198000,
    "trade_price": 160019000,
    "timestamp": 1754319597485,
    "candle_acc_trade_price": 76380029312.6095,
    "candle_acc_trade_volume": 476.84775713,
    "prev_closing_price": 159369000,
    "change_price": 650000,
    "change_rate": 0.0040785849,
    "converted_trade_price": null
  },
  {
    "market": "KRW-BTC",
    "candle_date_time_utc": "2025-08-02T15:00:00",
    "candle_date_time_kst": "2025-08-03T00:00:00",
    "opening_price": 158759000,
    "high_price": 160166000,
    "low_price": 156713000,
    "trade_price": 159369000,
    "timestamp": 1754233197709,
    "candle_acc_trade_price": 89662280878.97043,
    "candle_acc_trade_volume": 565.97495962,
    "prev_closing_price": 158760000,
    "change_price": 609000,
    "change_rate": 0.0038359788,
    "converted_trade_price": null
  },
  {
    "market": "KRW-BTC",
    "candle_date_time_utc": "2025-08-01T15:00:00",
    "candle_date_time_kst": "2025-08-02T00:00:00",
    "opening_price": 160179000,
    "high_price": 160300000,
    "low_price": 157863000,
    "trade_price": 158760000,
    "timestamp": 1754146797746,
    "candle_acc_trade_price": 106445851586.73428,
    "candle_acc_trade_volume": 670.85664804,
    "prev_closing_price": 160156000,
    "change_price": -1396000,
    "change_rate": -0.0087165014,
    "converted_trade_price": null
  },
  {
    "market": "KRW-BTC",
    "candle_date_time_utc": "2025-07-31T15:00:00",
    "candle_date_time_kst": "2025-08-01T00:00:00",
    "opening_price": 163402000,
    "high_price": 164174000,
    "low_price": 159091000,
    "trade_price": 160156000,
    "timestamp": 1754060398147,
    "candle_acc_trade_price": 177169847672.76746,
    "candle_acc_trade_volume": 1100.55553762,
    "prev_closing_price": 163402000,
    "change_price": -3246000,
    "change_rate": -0.0198651179,
    "converted_trade_price": null
  },
  {
    "market": "KRW-BTC",
    "candle_date_time_utc": "2025-07-30T15:00:00",
    "candle_date_time_kst": "2025-07-31T00:00:00",
    "opening_price": 163732000,
    "high_price": 163987000,
    "low_price": 161515000,
    "trade_price": 163402000,
    "timestamp": 1753973999900,
    "candle_acc_trade_price": 78106762441.35745,
    "candle_acc_trade_volume": 478.86038231,
    "prev_closing_price": 163732000,
    "change_price": -330000,
    "change_rate": -0.0020154887,
    "converted_trade_price": null
  },
  {
    "market": "KRW-BTC",
    "candle_date_time_utc": "2025-07-29T15:00:00",
    "candle_date_time_kst": "2025-07-30T00:00:00",
    "opening_price": 162811000,
    "high_price": 163742000,
    "low_price": 162100000,
    "trade_price": 163732000,
    "timestamp": 1753887597737,
    "candle_acc_trade_price": 62991331519.58784,
    "candle_acc_trade_volume": 386.67227496,
    "prev_closing_price": 162811000,
    "change_price": 921000,
    "change_rate": 0.0056568659,
    "converted_trade_price": null
  },
  {
    "market": "KRW-BTC",
    "candle_date_time_utc": "2025-07-28T15:00:00",
    "candle_date_time_kst": "2025-07-29T00:00:00",
    "opening_price": 161521000,
    "high_price": 163798000,
    "low_price": 161492000,
    "trade_price": 162811000,
    "timestamp": 1753801199994,
    "candle_acc_trade_price": 87802735430.58064,
    "candle_acc_trade_volume": 538.95475001,
    "prev_closing_price": 161574000,
    "change_price": 1237000,
    "change_rate": 0.0076559347,
    "converted_trade_price": null
  },
  {
    "market": "KRW-BTC",
    "candle_date_time_utc": "2025-07-27T15:00:00",
    "candle_date_time_kst": "2025-07-28T00:00:00",
    "opening_price": 161698000,
    "high_price": 162976000,
    "low_price": 161421000,
    "trade_price": 161574000,
    "timestamp": 1753714797400,
    "candle_acc_trade_price": 81726483722.68152,
    "candle_acc_trade_volume": 503.44177311,
    "prev_closing_price": 161653000,
    "change_price": -79000,
    "change_rate": -0.0004887011,
    "converted_trade_price": null
  }
]
```

---

## get_account_info

**설명**: 계좌 정보 조회 - 보유 자산 및 잔고 정보

**함수 호출**: `get_account_info()`

**입력 파라미터**:
```json
"없음"
```

**응답 타입**: list

**응답 길이**: 4555 문자

**캡처 시간**: 2025-08-26T00:27:13.409383

**응답 데이터**:
```json
[
  {
    "currency": "P",
    "balance": "4",
    "locked": "0",
    "avg_buy_price": "0",
    "avg_buy_price_modified": false,
    "unit_currency": "KRW"
  },
  {
    "currency": "KRW",
    "balance": "21480.49913",
    "locked": "28117.9145",
    "avg_buy_price": "0",
    "avg_buy_price_modified": false,
    "unit_currency": "KRW"
  },
  {
    "currency": "XRP",
    "balance": "0.00000035",
    "locked": "0",
    "avg_buy_price": "832",
    "avg_buy_price_modified": false,
    "unit_currency": "KRW"
  },
  {
    "currency": "XMR",
    "balance": "0.00003175",
    "locked": "0",
    "avg_buy_price": "122041",
    "avg_buy_price_modified": false,
    "unit_currency": "KRW"
  },
  {
    "currency": "TRX",
    "balance": "0.00000075",
    "locked": "0",
    "avg_buy_price": "59.35",
    "avg_buy_price_modified": false,
    "unit_currency": "KRW"
  },
  {
    "currency": "KNC",
    "balance": "0.00003065",
    "locked": "0",
    "avg_buy_price": "719",
    "avg_buy_price_modified": false,
    "unit_currency": "KRW"
  },
  {
    "currency": "GLM",
    "balance": "0.00002",
    "locked": "0",
    "avg_buy_price": "279",
    "avg_buy_price_modified": false,
    "unit_currency": "KRW"
  },
  {
    "currency": "GTO",
    "balance": "0.00007",
    "locked": "0",
    "avg_buy_price": "289",
    "avg_buy_price_modified": false,
    "unit_currency": "KRW"
  },
  {
    "currency": "XEM",
    "balance": "0.000028",
    "locked": "0",
    "avg_buy_price": "255.3",
    "avg_buy_price_modified": false,
    "unit_currency": "KRW"
  },
  {
    "currency": "CTXC",
    "balance": "0.00009405",
    "locked": "0",
    "avg_buy_price": "335",
    "avg_buy_price_modified": false,
    "unit_currency": "KRW"
  },
  {
    "currency": "TRUE",
    "balance": "0.00002625",
    "locked": "0",
    "avg_buy_price": "526",
    "avg_buy_price_modified": false,
    "unit_currency": "KRW"
  },
  {
    "currency": "ABT",
    "balance": "0.00009605",
    "locked": "0",
    "avg_buy_price": "282",
    "avg_buy_price_modified": false,
    "unit_currency": "KRW"
  },
  {
    "currency": "RNT",
    "balance": "0.0000138",
    "locked": "0",
    "avg_buy_price": "131",
    "avg_buy_price_modified": false,
    "unit_currency": "KRW"
  },
  {
    "currency": "PLX",
    "balance": "0.0000738",
    "locked": "0",
    "avg_buy_price": "194.2",
    "avg_buy_price_modified": false,
    "unit_currency": "KRW"
  },
  {
    "currency": "VET",
    "balance": "0.00444",
    "locked": "0",
    "avg_buy_price": "16.06",
    "avg_buy_price_modified": false,
    "unit_currency": "KRW"
  },
  {
    "currency": "BZNT",
    "balance": "0.00003531",
    "locked": "0",
    "avg_buy_price": "3.949",
    "avg_buy_price_modified": false,
    "unit_currency": "KRW"
  },
  {
    "currency": "WET",
    "balance": "0.00007932",
    "locked": "0",
    "avg_buy_price": "4.64",
    "avg_buy_price_modified": false,
    "unit_currency": "KRW"
  },
  {
    "currency": "BXA",
    "balance": "0.000012",
    "locked": "0",
    "avg_buy_price": "0",
    "avg_buy_price_modified": false,
    "unit_currency": "KRW"
  },
  {
    "currency": "MIX",
    "balance": "0.0000044",
    "locked": "0",
    "avg_buy_price": "2.045",
    "avg_buy_price_modified": false,
    "unit_currency": "KRW"
  },
  {
    "currency": "WIN",
    "balance": "0.000009",
    "locked": "0",
    "avg_buy_price": "0",
    "avg_buy_price_modified": false,
    "unit_currency": "KRW"
  },
  {
    "currency": "XSR",
    "balance": "0.00000135",
    "locked": "0",
    "avg_buy_price": "73.72",
    "avg_buy_price_modified": false,
    "unit_currency": "KRW"
  },
  {
    "currency": "APIX",
    "balance": "0.00007895",
    "locked": "0",
    "avg_buy_price": "77.8",
    "avg_buy_price_modified": false,
    "unit_currency": "KRW"
  },
  {
    "currency": "BASIC",
    "balance": "0.36299077",
    "locked": "0",
    "avg_buy_price": "6.382",
    "avg_buy_price_modified": false,
    "unit_currency": "KRW"
  },
  {
    "currency": "KAIA",
    "balance": "14.33628318",
    "locked": "0",
    "avg_buy_price": "339",
    "avg_buy_price_modified": false,
    "unit_currency": "KRW"
  },
  {
    "currency": "TEMCO",
    "balance": "0.00004132",
    "locked": "0",
    "avg_buy_price": "1.527",
    "avg_buy_price_modified": false,
    "unit_currency": "KRW"
  },
  {
    "currency": "BTT",
    "balance": "0.009",
    "locked": "0",
    "avg_buy_price": "0",
    "avg_buy_price_modified": false,
    "unit_currency": "KRW"
  },
  {
    "currency": "D",
    "balance": "0.00001343",
    "locked": "0",
    "avg_buy_price": "167.9",
    "avg_buy_price_modified": false,
    "unit_currency": "KRW"
  },
  {
    "currency": "HFT",
    "balance": "0.00005379",
    "locked": "0",
    "avg_buy_price": "561.5",
    "avg_buy_price_modified": false,
    "unit_currency": "KRW"
  },
  {
    "currency": "FLOKI",
    "balance": "0.00009393",
    "locked": "0",
    "avg_buy_price": "0.0264",
    "avg_buy_price_modified": false,
    "unit_currency": "KRW"
  },
  {
    "currency": "USDT",
    "balance": "0.00000068",
    "locked": "0",
    "avg_buy_price": "1367",
    "avg_buy_price_modified": false,
    "unit_currency": "KRW"
  },
  {
    "currency": "ZBCN",
    "balance": "234.5622299",
    "locked": "0",
    "avg_buy_price": "0",
    "avg_buy_price_modified": false,
    "unit_currency": "KRW"
  },
  {
    "currency": "VTHO",
    "balance": "0.00448146",
    "locked": "0",
    "avg_buy_price": "4.813",
    "avg_buy_price_modified": false,
    "unit_currency": "KRW"
  }
]
```

---

## get_order_list

**설명**: 주문 리스트 조회 - 현재 주문 상태 및 이력

**함수 호출**: `get_order_list()`

**입력 파라미터**:
```json
"없음"
```

**응답 타입**: list

**응답 길이**: 730 문자

**캡처 시간**: 2025-08-26T00:27:13.482602

**응답 데이터**:
```json
[
  {
    "uuid": "C0101000002440423556",
    "side": "bid",
    "ord_type": "limit",
    "price": "140283000",
    "state": "wait",
    "market": "KRW-BTC",
    "created_at": "2025-08-25T22:50:38+09:00",
    "volume": "0.0001",
    "remaining_volume": "0.0001",
    "reserved_fee": "35.07075",
    "remaining_fee": "35.07075",
    "paid_fee": "0",
    "locked": "14064.37075",
    "executed_volume": "0",
    "trades_count": 0
  },
  {
    "uuid": "C0101000002440297447",
    "side": "bid",
    "ord_type": "limit",
    "price": "140175000",
    "state": "wait",
    "market": "KRW-BTC",
    "created_at": "2025-08-25T20:31:10+09:00",
    "volume": "0.0001",
    "remaining_volume": "0.0001",
    "reserved_fee": "35.04375",
    "remaining_fee": "35.04375",
    "paid_fee": "0",
    "locked": "14053.54375",
    "executed_volume": "0",
    "trades_count": 0
  }
]
```

---

## get_order_chance

**설명**: 주문 가능 정보 조회 - BTC 거래 가능 정보 및 수수료

**함수 호출**: `get_order_chance(market)`

**입력 파라미터**:
```json
{
  "market": "KRW-BTC"
}
```

**응답 타입**: dict

**응답 길이**: 723 문자

**캡처 시간**: 2025-08-26T00:27:13.552492

**응답 데이터**:
```json
{
  "bid_fee": "0.0025",
  "ask_fee": "0.0025",
  "maker_bid_fee": "0.0025",
  "maker_ask_fee": "0.0025",
  "market": {
    "id": "KRW-BTC",
    "name": "BTC/KRW",
    "order_types": [
      "limit"
    ],
    "order_sides": [
      "ask",
      "bid"
    ],
    "bid_types": [
      "limit",
      "price"
    ],
    "ask_types": [
      "limit",
      "market"
    ],
    "bid": {
      "currency": "KRW",
      "min_total": "5000"
    },
    "ask": {
      "currency": "BTC",
      "min_total": "5000"
    },
    "max_total": "1000000000",
    "state": "active"
  },
  "bid_account": {
    "currency": "KRW",
    "balance": "21480.49913",
    "locked": "28117.9145",
    "avg_buy_price": "0",
    "avg_buy_price_modified": false,
    "unit_currency": "KRW"
  },
  "ask_account": {
    "currency": "BTC",
    "balance": "0",
    "locked": "0",
    "avg_buy_price": "0",
    "avg_buy_price_modified": false,
    "unit_currency": "KRW"
  }
}
```

---

## place_order_buy

**설명**: 매수 주문 생성 - 지정가 매수 주문 응답

**함수 호출**: `place_order(market, side, order_type, price, volume)`

**입력 파라미터**:
```json
{
  "market": "KRW-BTC",
  "side": "bid",
  "order_type": "limit",
  "price": 141705000,
  "volume": 0.0001
}
```

**응답 타입**: dict

**응답 길이**: 138 문자

**캡처 시간**: 2025-08-26T00:27:13.659805

**응답 데이터**:
```json
{
  "order_id": "C0101000002440517711",
  "market": "KRW-BTC",
  "side": "bid",
  "order_type": "limit",
  "created_at": "2025-08-26T00:27:13+09:00"
}
```

---

