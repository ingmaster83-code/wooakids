require 'json'

module Jekyll
  class KidsPageGenerator < Generator
    safe true
    priority :normal

    def generate(site)
      attractions = load_json(site, '_rawdata/attractions.json')

      Jekyll.logger.info "KidsGenerator:", "관광지 #{attractions.size}개"

      at_by_sido = group_by(attractions, 'sido')
      at_by_sgg  = group_by(attractions, 'sigungu')

      attractions.each do |at|
        next if at['slug'].to_s.strip.empty?
        sgg = at['sigungu'].to_s.strip
        nearby_ats = nearby_fill(
          (at_by_sgg[sgg] || []).reject { |a| a['slug'] == at['slug'] },
          (at_by_sido[at['sido']] || []).reject { |a| a['slug'] == at['slug'] },
          6
        )
        site.pages << AttractionPage.new(site, at, nearby_ats)
      end

      at_by_sido.keys.uniq.sort.each do |sido|
        next if sido.to_s.strip.empty?
        ats = at_by_sido[sido] || []

        site.pages << RegionPage.new(site, sido, '', ats)

        sgg_map = group_by(ats, 'sigungu')
        sgg_map.keys.uniq.sort.each do |sgg|
          next if sgg.to_s.strip.empty?
          site.pages << RegionPage.new(site, sido, sgg, sgg_map[sgg] || [])
        end
      end

      # 카테고리(유형)별 페이지
      type_groups = {
        'nature'   => { label: '자연/공원',      emoji: '🌿', cat2s: %w[A0101 A0102 A0202] },
        'history'  => { label: '역사/문화재',    emoji: '🏰', cat2s: %w[A0201] },
        'museum'   => { label: '박물관/문화시설', emoji: '🏛️', cat2s: %w[A0206] },
        'activity' => { label: '체험시설',       emoji: '🎨', cat2s: %w[A0203] },
        'sports'   => { label: '레포츠/캠핑',    emoji: '⛹️', cat2s: %w[A0302 A0303 A0304 A0305] },
        'landmark' => { label: '건축/랜드마크',  emoji: '🏗️', cat2s: %w[A0204 A0205] },
      }
      type_groups.each do |slug, info|
        items = attractions.select { |a| info[:cat2s].include?(a['cat2'].to_s) }
        site.pages << TypePage.new(site, slug, info[:label], info[:emoji], items)
      end
      site.pages << TypeIndexPage.new(site, type_groups)

      site.pages << SearchIndexPage.new(site, attractions)
      Jekyll.logger.info "KidsGenerator:", "완료"
    end

    private

    def load_json(site, path)
      file = File.join(site.source, path)
      return [] unless File.exist?(file)
      JSON.parse(File.read(file, encoding: 'utf-8'))
    rescue => e
      Jekyll.logger.warn "KidsGenerator:", "#{path} 로드 실패: #{e.message}"
      []
    end

    def nearby_fill(primary, fallback, limit)
      result = primary.first(limit)
      if result.size < limit
        extra = fallback.reject { |x| result.any? { |r| r['slug'] == x['slug'] } }
        result += extra.first(limit - result.size)
      end
      result
    end

    def group_by(items, key)
      result = {}
      items.each do |item|
        k = item[key].to_s.strip
        next if k.empty?
        (result[k] ||= []) << item
      end
      result
    end
  end

  # ── 관광지 상세 ──────────────────────
  class AttractionPage < Page
    def initialize(site, at, nearby_ats)
      @site = site
      @base = site.source
      @dir  = "attraction/#{at['slug']}"
      @name = 'index.html'

      self.process(@name)
      self.read_yaml(File.join(@base, '_layouts'), 'attraction.html')
      self.data.merge!(at)
      self.data['layout']       = 'attraction'
      self.data['facilityName'] = at['name']
      self.data['title']        = "#{at['name']} 아이랑 갈만한 곳"
      self.data['description']  = build_at_desc(at)
      self.data['nearby_ats']   = nearby_ats.map { |a| slim_at(a) }
    end

    private

    def build_at_desc(at)
      return at['seoDescription'] if at['seoDescription'].to_s.length > 10
      label = at['contentTypeLabel'] || '시설'
      addr  = at['address'] || ''
      "#{at['name']} #{addr} 아이랑 갈만한 #{label}. 우아키즈에서 위치, 운영정보를 확인하세요."[0, 155]
    end

    def slim_at(a)
      { 'slug' => a['slug'], 'facilityName' => a['name'],
        'address' => a['address'], 'contentType' => a['contentType'],
        'contentTypeLabel' => a['contentTypeLabel'], 'firstImage' => a['firstImage'] }
    end
  end

  # ── 지역별 페이지 ──────────────────────
  class RegionPage < Page
    def initialize(site, sido, sigungu, attractions)
      @site = site
      @base = site.source

      slug_sido = sido.gsub(/\s+/, '')
      if sigungu.to_s.strip.empty?
        @dir      = "region/#{slug_sido}"
        title_loc = sido
      else
        @dir      = "region/#{slug_sido}/#{sigungu.gsub(/\s+/, '')}"
        title_loc = "#{sido} #{sigungu}"
      end
      @name = 'index.html'

      self.process(@name)
      self.read_yaml(File.join(@base, '_layouts'), 'region.html')
      self.data['layout']      = 'region'
      self.data['sido']        = sido
      self.data['sigungu']     = sigungu.to_s
      self.data['title']       = "#{title_loc} 아이랑 갈만한 곳"
      self.data['description'] = "#{title_loc} 아이랑 갈만한 관광지·문화시설·레포츠 #{attractions.size}개 정보."
      self.data['attractions'] = attractions.first(60).map do |a|
        { 'slug' => a['slug'], 'facilityName' => a['name'],
          'address' => a['address'], 'contentType' => a['contentType'],
          'contentTypeLabel' => a['contentTypeLabel'] }
      end
      self.data['at_count'] = attractions.size
    end
  end

  # ── 유형별 페이지 ──────────────────────
  class TypePage < Page
    def initialize(site, slug, label, emoji, attractions)
      @site = site
      @base = site.source
      @dir  = "type/#{slug}"
      @name = 'index.html'

      self.process(@name)
      self.read_yaml(File.join(@base, '_layouts'), 'type.html')
      self.data['layout']      = 'type'
      self.data['type_slug']   = slug
      self.data['type_label']  = label
      self.data['type_emoji']  = emoji
      self.data['title']       = "#{label} 아이랑 갈만한 곳"
      self.data['description'] = "아이와 함께 방문하기 좋은 #{label} 시설 #{attractions.size}곳을 한눈에. 우아키즈에서 위치와 상세정보를 확인하세요."
      self.data['attractions'] = attractions.map do |a|
        { 'slug' => a['slug'], 'facilityName' => a['name'],
          'address' => a['address'], 'sido' => a['sido'],
          'contentType' => a['contentType'], 'contentTypeLabel' => a['contentTypeLabel'],
          'firstImage' => a['firstImage'] }
      end
      self.data['at_count'] = attractions.size
    end
  end

  # ── 유형별 인덱스 ──────────────────────
  class TypeIndexPage < Page
    def initialize(site, type_groups)
      @site = site
      @base = site.source
      @dir  = 'type'
      @name = 'index.html'

      self.process(@name)
      self.read_yaml(File.join(@base, '_layouts'), 'type_index.html')
      self.data['layout']      = 'type_index'
      self.data['title']       = '유형별로 찾기 - 우아키즈'
      self.data['description'] = '박물관, 역사, 자연, 체험, 레포츠 등 유형별로 아이랑 갈만한 곳을 찾아보세요.'
      self.data['type_groups'] = type_groups.map do |slug, info|
        { 'slug' => slug, 'label' => info[:label], 'emoji' => info[:emoji] }
      end
    end
  end

  # ── 검색 인덱스 ──────────────────────
  class SearchIndexPage < Page
    def initialize(site, attractions)
      @site = site
      @base = site.source
      @dir  = ''
      @name = 'search_index.json'

      self.process(@name)
      self.data = { 'layout' => nil, 'sitemap' => false }

      at_index = attractions.map do |at|
        { 'type' => 'attraction', 'slug' => at['slug'],
          'name' => at['name'], 'sido' => at['sido'],
          'address' => at['address'], 'typeLabel' => at['contentTypeLabel'],
          'firstImage' => at['firstImage'] }
      end

      self.content = at_index.to_json
    end

    def output   = self.content
    def render(layouts, registers); end
  end
end
