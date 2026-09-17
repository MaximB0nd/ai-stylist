# Аудит иллюстраций выбора (FRONT-10)

Дата: 16 сентября 2026. Проверены все 16 изображений страницы `/generation`:
соответствие подписи, различимость внутри группы, читаемость миниатюры,
единый стиль и пропорции. Это визуальная экспертная оценка, не пользовательское
тестирование. Общая палитра, интерфейс и поведение формы не меняются.

| Вариант | Решение и причина |
| --- | --- |
| Улица | Заменён стул с сумкой и кофе: он больше ассоциировался с кафе. Скамейка, уличный фонарь и мощение явно показывают прогулочную среду. |
| Учёба | Во втором проходе заменены закрытые книги с бантом: возможна ассоциация с подарком. Теперь открытый учебник, спиральная тетрадь и карандаш; внешний силуэт важнее мелких линий страниц. |
| Офис | Заменена сумка с ежедневником: сумка повторялась в других группах и не обозначала место. По дополнительному запросу массивный деревянный стол заменён современным светлым столом на тонком металлическом каркасе, ноутбуком и сетчатым креслом. |
| Вечер | Оставлены бархатный клатч и свеча: совместно передают вечерний выход. |
| Минимализм | Во втором проходе заменён светлый комплект: топ терялся на фоне. Теперь серый однотонный топ и тёмные прямые брюки, разложенные на поверхности; силуэт контрастнее, чем раньше, без добавления декора. |
| Классика | Оставлен структурный жакет: отличается кроем от остальных стилей. |
| Casual | Оставлены джинсы и полосатый трикотаж: читаемый повседневный комплект. |
| Романтичный | Оставлено платье с мягкими складками и оборками. |
| Кроссовки | Оставлен кроссовок: видны шнуровка и характерная подошва. |
| Лоферы | Оставлен лофер: видны перемычка и отсутствие шнуровки. |
| Каблук | Оставлена туфля: хорошо читается высокий каблук. |
| Ботинки | Оставлен ботинок: закрытая щиколотка отличает его от туфли. |
| Уверенное | Во втором проходе сумка заменена сложенным тёмным жакетом, ремнём и угловатыми очками. Строгие линии отличаются от мягкого трикотажа и платка. Это по-прежнему условная ассоциация, не универсальное обозначение уверенности. |
| Элегантное | Оставлены шёлковый платок и серьги: деликатные материалы и линии. |
| Расслабленное | Оставлены мягкий кардиган и чашка: ассоциация с комфортом. |
| Яркое | Во втором проходе заменена коралловая сумка: её отличие слишком зависело от цвета. Теперь сложенная блуза с крупным светло-тёмным геометрическим принтом и выразительные серьги; есть отличие по узору и форме. |

Подписи сохранены у всех вариантов. Особенно важно не заменять абстрактные
впечатления изображениями без текста. `alt=""` у иллюстраций намеренный:
доступное имя переключателя уже задаётся видимой подписью в `label`.

## Новые файлы

Встроенный `image_gen`, по одному вызову на изображение. Исходники PNG
1254 × 1254 px сохранены инструментом вне репозитория. Для сайта из них
получены WebP 400 × 400 px, quality 86: только пропорциональное уменьшение
и кодирование через bundled Sharp, без обрезки, дорисовки или новых зависимостей.

- `src/frontend/public/images/generation/occasion-street.webp`: 21 342 байта.
  Исходник: `exec-3067d399-3738-4e52-bff2-19752c531963.png`.
- `src/frontend/public/images/generation/occasion-office.webp`: 14 480 байт.
  Актуальный исходник: `exec-819d71b5-d9f7-42c6-8565-aa9a21ac1116.png`.
- `src/frontend/public/images/generation/occasion-study.webp`: 19 824 байта.
  Исходник: `exec-739d5a24-50b9-4b1b-9565-95ca8e5bac31.png`.
- `src/frontend/public/images/generation/style-minimal.webp`: 16 488 байт.
  Исходник: `exec-50a5ea48-9dc9-42a3-bfba-b5c161f2df45.png`.
- `src/frontend/public/images/generation/mood-confident.webp`: 26 156 байт.
  Исходник: `exec-cf349f32-401c-469e-a68c-034109bd31b5.png`.
- `src/frontend/public/images/generation/mood-bright.webp`: 23 512 байт.
  Исходник: `exec-3bd5ae56-faeb-4e19-8b5f-cbc7e10654c9.png`.

Имена файлов сохранены. Python добавляет к URL вариантов ответа
`?v=3` через `CHOICE_IMAGE_VERSION`: значение нужно повышать при следующей
замене набора. Это устраняет показ прежних картинок из браузерного кэша.
JavaScript сводки уже копирует полный URL, его поведение не изменено.

## Спецификации промптов

Общие требования: square editorial watercolor, softly textured ivory paper
background reaching all edges, realistic hand-painted objects, restrained
wood / charcoal / burgundy palette, complete subjects inside the square,
soft ground shadows, readable at thumbnail size. No people, mannequins,
headless figures, text, logos, watermark, border or UI framing.

- Street: outdoor wooden park bench with a backrest and dark wrought iron
  legs, one slender streetlamp behind its right side, a small patch of pale
  stone pavement. Bench dominates the foreground in three-quarter view;
  compact composition, minimal foliage, no café table, coffee or handbag.
  Style references: original `occasion-street.webp` and `occasion-study.webp`.
- Office (revised): modern minimalist desk with a thin light ash tabletop
  and slender matte charcoal metal legs, slim open silver laptop, light gray
  mesh ergonomic swivel chair and one small dusty-rose notebook. Three-quarter
  view, all legs visible, compact square composition. Preserve watercolor and
  ivory background; no drawers, heavy brown wood, vintage furniture, clutter,
  people, lettering or logos. Style reference: previous generated office image.
- Study: open textbook with sparse non-readable printed lines and a small
  geometry diagram, spiral-bound blank notebook and graphite pencil. Three
  objects only, clear outer edges, no ribbons, bows, laptop or readable text.
  Style reference: original `occasion-study.webp`.
- Minimalism: flat lay of a plain warm-gray short-sleeved crew-neck top and
  charcoal straight trousers folded lengthwise. Clearly separated from ivory
  background, no accessories, pattern, logos, belt or hanger. Not worn or
  arranged as a body. References: original `style-minimal.webp`, `style-casual.webp`.
- Confident: overhead flat lay of folded charcoal blazer with pointed lapels,
  angular sunglasses and rolled burgundy belt with rectangular brass buckle.
  Crisp angular lines, no handbag, person or invisible mannequin.
  References: original `mood-confident.webp`, `style-casual.webp`.
- Bright: flat folded silk blouse with large irregular ivory, charcoal, coral
  and dusty rose geometric shapes and statement brass earrings. Distinction
  through large light-dark pattern, not hue alone; no stripes or tiny busy print.
  References: original `mood-bright.webp`, `style-casual.webp`.

## Доступность выбора

- У всех 16 вариантов сохранены видимые подписи внутри `label`, нативные
  `radio` и группировка `fieldset` / `legend`. Названия и состояния проверены
  в accessibility tree Chromium, без запуска отдельного скринридера.
- Пройдены все 16 вариантов стрелками клавиатуры: фокус следует выбору,
  вокруг карточки появляется контур 2 px, сводка обновляет картинку и подпись.
  Заполненный радио-индикатор отличает выбор не только изменением цвета.
- Добавлен регрессионный тест текстовых подписей, пустого `alt`, нативных
  доступных для выбора полей, квадратных размеров и версии URL всех карточек.
- Слабовидение и особенности цветовосприятия не компенсируются одной
  регенерацией: подписи обязательны, а понимание абстрактных впечатлений
  требует проверки с реальными пользователями. Полное соответствие WCAG
  и работа во всех скринридерах этим аудитом не подтверждаются.

Основания: [W3C WAI: изображения с текстом в элементе управления](https://www.w3.org/WAI/tutorials/images/functional/#example-2-logo-image-within-link-text)
и [WCAG: смысл не должен зависеть только от цвета](https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html).

Стилизация новых изображений согласована с исходным набором; они не являются
фотографиями реальных товаров или мест. Права на оставшиеся исходные изображения
из HTML-макета команда по-прежнему должна проверить перед публичным запуском.
