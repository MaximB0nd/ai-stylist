from casp.layout import Metadata

from src.components.shared.layout.app_shell import app_shell

metadata = Metadata(
    title="Новые образы",
    description="Заполните данные для генерации образов",
)



def page():
    return app_shell(
        r"""
    <section class="main-content">
        <div class="content-wrapper">

            <header class="gallery-header">
                <h1 class="gallery-title">Галерея</h1>
                <a href="/generation" class="btn-new-album">
                    <span class="btn-plus">+</span>
                    Новые образы
                </a>
            </header>

            <div class="gallery-filters">
                <div class="filters-tabs">
                    <button class="filter-tab active" data-filter="all">Все <span>4</span></button>
                    <button class="filter-tab" data-filter="active">Активные <span>3</span></button>
                    <button class="filter-tab" data-filter="archive">Архив <span>1</span></button>
                </div>
                <div class="filters-count">4 альбома</div>
            </div>

            <div class="albums-grid">

                <a href="/album/office" class="album-card">
                    <div class="album-preview">
                        <div class="album-image image-office"></div>
                        <span class="album-badge">10 образов</span>
                    </div>
                    <div class="album-footer">
                        <div class="album-meta">
                            <div class="album-name">Офис</div>
                            <div class="album-date">5 сентября 2026</div>
                        </div>
                        <div class="album-arrow">→</div>
                    </div>
                </a>

                <a href="/album/evening" class="album-card">
                    <div class="album-preview">
                        <div class="album-image image-evening"></div>
                        <span class="album-badge">10 образов</span>
                    </div>
                    <div class="album-footer">
                        <div class="album-meta">
                            <div class="album-name">Вечер</div>
                            <div class="album-date">3 сентября 2026</div>
                        </div>
                        <div class="album-arrow">→</div>
                    </div>
                </a>

                <a href="/album/street" class="album-card active">
                    <div class="album-preview">
                        <div class="album-image image-street"></div>
                        <span class="album-badge">10 образов</span>
                    </div>
                    <div class="album-footer">
                        <div class="album-meta">
                            <div class="album-name">Улица</div>
                            <div class="album-date">1 сентября 2026</div>
                        </div>
                        <div class="album-arrow filled">→</div>
                    </div>
                </a>

                <a href="/album/study" class="album-card archived">
                    <div class="album-preview">
                        <div class="album-image image-study"></div>
                        <span class="album-badge">10 образов</span>
                        <span class="album-archive-label">В архиве</span>
                    </div>
                    <div class="album-footer">
                        <div class="album-meta">
                            <div class="album-name">Учёба</div>
                            <div class="album-date">28 августа 2026</div>
                        </div>
                        <div class="album-arrow">→</div>
                    </div>
                </a>

            </div>

        </div>
</section>
""",
        title="Галерея",
    )
