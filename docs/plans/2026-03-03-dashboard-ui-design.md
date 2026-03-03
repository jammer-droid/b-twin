# B-TWIN Dashboard UI Design

Date: 2026-03-03
Status: Approved

## 1. Design Concept: "Observatory"

A warm, explorative space observatory aesthetic. The UI feels like observing the cosmos from a control station — deep navy backgrounds with warm amber and violet accents that evoke starlight and nebulae.

### Core Metaphor

| Domain Concept | Space Metaphor |
|----------------|----------------|
| Entry (note) | Planet |
| Related links | Orbital connections |
| Source/Project | Galaxy |
| Graph view | Star chart / Constellation map |
| Quick Capture | Comet trail |
| Session | Mission log |

### Design Principles

1. **Minimal with warmth** — Clean layout (Linear-style), but warm cosmic palette instead of cold grays
2. **Subtle SF accents** — Space theme expressed through colors, icons, and glow effects, not heavy illustrations
3. **Dimensionality** — SVG gradients for depth (planet-like nodes), micro glow effects on interactions
4. **All vector** — No raster images; CSS gradients, SVG, and code-based visuals only
5. **Dark only** — Single dark theme optimized for the cosmic aesthetic

## 2. Color System

### Base

| Token | Hex | Usage |
|-------|-----|-------|
| `bg-primary` | `#0B1120` | App background (deep night sky) |
| `bg-surface` | `#111827` | Cards, panels |
| `bg-elevated` | `#1F2937` | Hover states, active surfaces |
| `border-default` | `#1F2937` | Subtle dividers |

### Accents

| Token | Hex | Usage |
|-------|-----|-------|
| `accent-amber` | `#F59E0B` | Primary actions, highlights, active states (starlight) |
| `accent-violet` | `#8B5CF6` | Secondary actions, tags, sessions (nebula) |
| `accent-blue` | `#3B82F6` | Links, informational elements (deep space) |

### Text

| Token | Hex | Usage |
|-------|-----|-------|
| `text-primary` | `#F9FAFB` | Headings, primary content |
| `text-secondary` | `#9CA3AF` | Descriptions, metadata |
| `text-muted` | `#6B7280` | Timestamps, placeholders |

### Glow Effects

- Card hover: `box-shadow: 0 0 20px rgba(245, 158, 11, 0.08)`
- Active sidebar item: 2px left border `accent-amber` + subtle glow
- Graph nodes: SVG `radialGradient` for planetary depth

## 3. Layout

### Structure

```
Sidebar (56px, icon bar) + Main Content (fluid)
```

- **Sidebar**: Narrow icon bar (56px), tooltip on hover, bottom-anchored settings
- **Main content**: 24px padding, fluid width

### Active Sidebar Indicator

- Left 2px amber border + amber icon color

### Pages (from Product Spec IA)

1. **Home** — Quick Capture input + Recent Entries grid + Recent Sessions grid
2. **Entries** — Search/filter bar + Entry list (left) + Detail side panel (right)
3. **Sessions** — Session history list + session detail
4. **Summary** — summary.md viewer/editor
5. **Sources** — Source list with enable/disable toggles, scan trigger
6. **Graph** — Constellation-style node graph (promoted to MVP)

## 4. Page Layouts

### Home

```
┌──────────────────────────────────────────┐
│  Quick Capture                           │
│  ┌────────────────────────────────────┐  │
│  │ What's on your mind?              │  │
│  └────────────────────────────────────┘  │
│  [Save]                                  │
├────────────────────┬─────────────────────┤
│  Recent Entries    │  Recent Sessions    │
│  ┌──────────────┐  │  ┌──────────────┐  │
│  │ entry card   │  │  │ session card │  │
│  │ entry card   │  │  │ session card │  │
│  │ entry card   │  │  │ session card │  │
│  └──────────────┘  │  └──────────────┘  │
└────────────────────┴─────────────────────┘
```

### Entries (List + Side Panel)

```
┌─────────────────────┬────────────────────┐
│  Search + Filters   │                    │
│  ┌────────────────┐ │   Entry Detail     │
│  │ entry row      │ │   (Side Panel)     │
│  │ entry row  ◀── │ │                    │
│  │ entry row      │ │   Title            │
│  │ entry row      │ │   Metadata badges  │
│  │ entry row      │ │   ─────────────    │
│  │                │ │   Markdown body    │
│  └────────────────┘ │                    │
└─────────────────────┴────────────────────┘
```

## 5. Component Patterns

### Card

- Background: `bg-surface` (`#111827`)
- Border: `1px solid border-default`
- Border radius: `12px`
- Padding: `16px`
- Hover: subtle amber glow

### Entry Row (in list)

- Compact: title + topic badge + date
- Selected: `bg-elevated` background + left amber indicator

### Badge/Tag

- Background: accent color at 15% opacity
- Text: accent color
- Border radius: `6px`
- Font: 11px / 500

### Search Bar

- Full-width input with search icon
- Background: `bg-surface`
- Focus: amber border glow

## 6. Typography

### Fonts

- **Primary**: Inter (sans-serif)
- **Monospace**: JetBrains Mono (slugs, code)

### Scale

| Usage | Size | Weight |
|-------|------|--------|
| Page Title | 24px | 600 (Semibold) |
| Section Title | 18px | 600 |
| Card Title | 14px | 500 (Medium) |
| Body | 14px | 400 (Regular) |
| Caption/Metadata | 12px | 400 |
| Badge/Tag | 11px | 500 |

## 7. Iconography

- **Library**: Lucide Icons (lightweight, consistent stroke, React-friendly)
- **Sizes**: Sidebar 20px, Inline 16px

### Menu Icon Mapping

| Page | Icon | Space Metaphor |
|------|------|----------------|
| Home | `Orbit` | Central hub |
| Entries | `FileText` | Knowledge planets |
| Sessions | `Timer` | Mission logs |
| Summary | `BookOpen` | Observatory journal |
| Sources | `Database` | Galaxy sources |
| Graph | `Network` | Constellation map |
| Settings | `Settings` | Control panel |

## 8. Graph Page Layout

```
┌──────────────────────────────────────────┐
│  Knowledge Graph            [Filters ▾]  │
│  ┌────────────────────────────────────┐  │
│  │                                    │  │
│  │     ◉───────◉                     │  │
│  │    /         \                     │  │
│  │   ◉     ◉────◉                    │  │
│  │    \   /                           │  │
│  │     ◉─◉          ◉──◉             │  │
│  │                  /                 │  │
│  │                 ◉                  │  │
│  │                                    │  │
│  └────────────────────────────────────┘  │
│  Metadata match: [──●──] threshold        │
└──────────────────────────────────────────┘
```

### Graph Design Details

- **Nodes**: Entries rendered as planet-style illustrations
  - **Asset strategy**: Flat illustrative SVG planet assets (warm, dimensional feel). Created separately in Figma/Illustrator/AI tool — not code-generated.
  - Reference style: [vecteezy comet-around-planet](https://www.vecteezy.com/vector-art/68639466) — simple but visually distinct, warm colors with depth
  - Size scaled by connection count or importance
  - Color mapped by topic/source (amber, violet, blue palette)
  - Hover: glow effect + entry title tooltip
  - Click: opens entry detail panel
- **Edges**: Orbital connection lines between `related` entries
  - Explicit links (`related` field): solid lines (amber)
  - Metadata match candidates: dashed lines (gray, based on `tags`/`topic`/`project` overlap)
- **Controls**:
  - Filter by topic, tags, source
  - Metadata match threshold slider
  - Zoom / pan (scroll + drag)
- **Future**: Vector similarity overlay (ChromaDB-based, deferred)
- **Implementation**: Canvas-based (e.g., D3.js force-directed or react-force-graph)

## 9. Visual Effects & Interactions

Observatory 컨셉에 맞는 시각 효과 카탈로그. 구현 시 선택적으로 적용.

### Tier 1: 기본 인터랙션 (CSS Transitions)

낮은 공수로 체감 효과 높은 것들. MVP에 포함 권장.

| 효과 | 적용 위치 | 구현 방식 | 설명 |
|------|-----------|-----------|------|
| 호버 글로우 | 카드, 사이드바 아이콘 | CSS `box-shadow` transition | 마우스 오버 시 amber 글로우 발생 |
| 입력 포커스 글로우 | Quick Capture, Search Bar | CSS `border-color` + `box-shadow` | 포커스 시 amber 보더 빛남 |
| 토글 슬라이드 | Sources 토글 스위치 | CSS `transform` transition | On/Off 전환 시 부드러운 노브 이동 |
| 버튼 프레스 | Save, Scan 버튼 | CSS `transform: scale(0.97)` | 클릭 시 살짝 눌리는 피드백 |
| 사이드바 툴팁 | 사이드바 아이콘 | CSS tooltip on hover | 아이콘 호버 시 페이지 이름 표시 |

### Tier 2: 전환 애니메이션 (Framer Motion)

페이지/패널 전환에 생동감. 라이브러리 의존.

| 효과 | 적용 위치 | 구현 방식 | 설명 |
|------|-----------|-----------|------|
| 페이지 전환 | 사이드바 네비게이션 | Framer Motion `AnimatePresence` | fade + 미세한 slide 전환 |
| 사이드 패널 슬라이드 | Entries 상세 패널 | Framer Motion `animate` | 오른쪽에서 슬라이드 인 |
| 카드 등장 | Home 최근 엔트리/세션 | Framer Motion `staggerChildren` | 카드가 순차적으로 fade-in |
| 리스트 아이템 전환 | Entries 리스트 | Framer Motion `layout` | 필터 변경 시 부드럽게 재배치 |
| 알림/토스트 | 저장 완료 등 | Framer Motion slide + fade | 하단에서 올라오는 알림 |

### Tier 3: 배경 & 분위기 (Canvas/CSS)

Observatory 테마의 몰입감. 성능 영향 고려 필요.

| 효과 | 적용 위치 | 구현 방식 | 설명 |
|------|-----------|-----------|------|
| 별 파티클 배경 | 전체 앱 배경 | Canvas 또는 CSS `box-shadow` | 느리게 떠다니는 미세한 점들. opacity 낮게 |
| 미세한 성운 그라데이션 | 배경 코너 | CSS `radial-gradient` animation | 배경에 은은하게 움직이는 컬러 블러 |
| 슬라이더 트랙 글로우 | Similarity/Match 슬라이더 | CSS gradient on track | 슬라이더 값에 따라 트랙 색상 변화 |

### Tier 4: 그래프 전용 (D3.js / react-force-graph)

Knowledge Graph 페이지의 핵심 인터랙션.

| 효과 | 적용 위치 | 구현 방식 | 설명 |
|------|-----------|-----------|------|
| Force-directed 물리 | 그래프 캔버스 | D3 force simulation | 노드 간 반발력/인력으로 자연스러운 배치 |
| 노드 드래그 | 그래프 노드 | D3 drag behavior | 노드를 잡아 끌면 물리 시뮬 반응 |
| 줌/패닝 | 그래프 캔버스 | D3 zoom | 스크롤로 줌, 드래그로 패닝 |
| 노드 호버 | 그래프 노드 | SVG scale + glow | 호버 시 노드 확대 + 연결선 하이라이트 |
| 노드 출현 | 새 엔트리 추가 시 | SVG scale animation | 새 노드가 0 → 1 스케일로 등장 |
| 연결선 드로잉 | related 링크 생성 시 | SVG `stroke-dashoffset` animation | 궤도선이 그려지는 효과 |
| 클러스터 하이라이트 | 필터 적용 시 | opacity transition | 선택된 그룹만 밝게, 나머지 dim |

### 성능 가이드라인

- Tier 1~2는 성능 영향 거의 없음 → MVP에 자유롭게 사용
- Tier 3 별 파티클: `requestAnimationFrame` + 30fps 제한 권장
- Tier 4 그래프: 노드 100개 이하에서는 문제없음. 이상이면 WebGL 렌더러(react-force-graph-3d) 고려
- 모든 애니메이션은 `prefers-reduced-motion` 미디어 쿼리 존중

### 권장 라이브러리

| 용도 | 라이브러리 |
|------|-----------|
| 전환 애니메이션 | `framer-motion` |
| 그래프 시각화 | `react-force-graph-2d` 또는 `d3-force` |
| 파티클 배경 | 순수 Canvas API (의존성 최소화) |

## 10. Tech Stack

| Layer | Choice |
|-------|--------|
| Framework | React |
| Build | Vite |
| Language | TypeScript |
| Styling | TailwindCSS |
| Backend | FastAPI (Python) |
| Theme | Dark only |
| Deployment | `btwin ui` (local server) |

## 11. Mockups

- **File**: `docs/pencil/dashboard.pen`
- **Pages**: Home, Entries, Sources, Graph (4 screens)

## 12. References

### MVP 적용

| 레퍼런스 | 링크 | 적용 포인트 |
|----------|------|-------------|
| D3 Force-Directed Graph | https://observablehq.com/@d3/force-directed-graph | 그래프 엔진 기본형. force 레이아웃의 표준 구현 |
| Obsidian Graph View | https://help.obsidian.md/plugins/graph | local/global view 분리, 필터 패널 구조, 1-2 hop 하이라이트 |
| Cosmograph | https://cosmograph.app/ | 다크 배경 노드 glow 강도 기준, 줌 레벨별 라벨 노출 단계 |
| Framer Motion | https://www.framer.com/motion/ | Tier2 모션(페이지 전환, 사이드 패널 슬라이드, 카드 등장) |

### Future 참고

| 레퍼런스 | 링크 | 참고 포인트 |
|----------|------|-------------|
| Graphistry Gallery | https://www.graphistry.com/gallery | 대규모 그래프 가독성: edge opacity, 군집 강조, 필터 UX |
| Logseq Graph | https://docs.logseq.com/ | 양방향 링크 탐색 인터랙션 (v2 벡터 유사도 도입 시 참고) |
| Stellarium Web | https://stellarium-web.org/ | 별지도 인터랙션 무드. "배경은 조용하게, 데이터 전면에" 원칙 |
| NASA Image Library | https://images.nasa.gov/ | 팔레트 참고(네이비+앰버+바이올렛 그라디언트 톤) |
| Vanta.js | https://www.vantajs.com/ | Tier3 배경 효과 아이디어 (별 파티클 등, 성능 주의) |

## 13. Next Steps

1. ~~Create UI mockups in Pencil~~ (Done)
2. ~~Validate mockups with user~~ (Done — iterating)
3. Create graph node SVG assets (separate illustration tool)
4. Create implementation plan
5. Build React frontend
