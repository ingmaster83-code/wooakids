require 'json'

module Jekyll
  class KidsPageGenerator < Generator
    safe true
    priority :normal

    def generate(site)
      playgrounds = load_json(site, '_rawdata/playgrounds.json')
      attractions = load_json(site, '_rawdata/attractions.json')

      Jekyll.logger.info "KidsGenerator:", "놀이시설 #{playgrounds.size}개, 관광지 #{attractions.size}개"

      # sido별 인덱스 (주변 시설용)
      pg_by_sido  = group_by(playgrounds, 'sido')
      at_by_sido  = group_by(attractions, 'sido')
      pg_by_sgg   = group_by(playgrounds, 'sigungu')
      at_by_sgg   = group_by(attractions, 'sigungu')

      playgrounds.each do |pg|
        next if pg['slug'].to_s.strip.empty?
        sgg = pg['sigungu'].to_s.strip
        # 같은 시군구 우선, 부족하면 같은 시도로 채움
        nearby_pgs = nearby_fill(
          (pg_by_sgg[sgg] || []).reject { |p| p['slug'] == pg['slug'] },
          (pg_by_sido[pg['sido']] || []).reject { |p| p['slug'] == pg['slug'] },
          6
        )
        nearby_ats = nearby_fill(
          (at_by_sgg[sgg] || []),
          (at_by_sido[pg['sido']] || []),
          4
        )
        site.pages << PlaygroundPage.new(site, pg, nearby_pgs, nearby_ats)
      end

      attractions.each do |at|
        next if at['slug'].to_s.strip.empty?
        sgg = at['sigungu'].to_s.strip
        nearby_ats = nearby_fill(
          (at_by_sgg[sgg] || []).reject { |a| a['slug'] == at['slug'] },
          (at_by_sido[at['sido']] || []).reject { |a| a['slug'] == at['slug'] },
          6
        )
        nearby_pgs = nearby_fill(
          (pg_by_sgg[sgg] || []),
          (pg_by_sido[at['sido']] || []),
          4
        )
        site.pages << AttractionPage.new(site, at, nearby_ats, nearby_pgs)
      end

      all_sidos = (pg_by_sido.keys + at_by_sido.keys).uniq.sort
      all_sidos.each do |sido|
        next if sido.to_s.strip.empty?
        pgs = pg_by_sido[sido] || []
        ats = at_by_sido[sido] || []

        site.pages << RegionPage.new(site, sido, '', pgs, ats)

        pg_by_sgg = group_by(pgs, 'sigungu')
        at_by_sgg = group_by(ats, 'sigungu')
        (pg_by_sgg.keys + at_by_sgg.keys).uniq.sort.each do |sgg|
          next if sgg.to_s.strip.empty?
          site.pages << RegionPage.new(site, sido, sgg,
            pg_by_sgg[sgg] || [], at_by_sgg[sgg] || [])
        end
      end

      site.pages << SearchIndexPage.new(site, playgrounds, attractions)
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

  # ── 놀이시설 상세 ──────────────────────
  class PlaygroundPage < Page
    def initialize(site, pg, nearby_pgs, nearby_ats)
      @site = site
      @base = site.source
      @dir  = "playground/#{pg['slug']}"
      @name = 'index.html'

      self.process(@name)
      self.read_yaml(File.join(@base, '_layouts'), 'playground.html')
      self.data.merge!(pg)
      self.data['layout']        = 'playground'
      self.data['facilityName']  = pg['name']
      self.data['title']         = "#{pg['name']} 위치 안전검사 현황"
      self.data['description']   = build_pg_desc(pg)
      self.data['nearby_pgs']    = nearby_pgs.map { |p| slim_pg(p) }
      self.data['nearby_ats']    = nearby_ats.map { |a| slim_at(a) }
    end

    private

    def build_pg_desc(pg)
      return pg['seoDescription'] if pg['seoDescription'].to_s.length > 10
      addr   = pg['address'] || ''
      place  = pg['instlPlace'] || ''
      safety = pg['safetyPass'] == 'Y' ? '안전검사 합격' : '안전검사 정보'
      "#{pg['name']} #{addr} 어린이 놀이시설 #{place} #{safety} 현황을 확인하세요."[0, 155]
    end

    def slim_pg(p)
      { 'slug' => p['slug'], 'facilityName' => p['name'],
        'address' => p['address'], 'instlPlace' => p['instlPlace'],
        'safetyStatus' => p['safetyStatus'] }
    end

    def slim_at(a)
      { 'slug' => a['slug'], 'facilityName' => a['name'],
        'address' => a['address'], 'contentType' => a['contentType'],
        'contentTypeLabel' => a['contentTypeLabel'] }
    end
  end

  # ── 관광지 상세 ──────────────────────
  class AttractionPage < Page
    def initialize(site, at, nearby_ats, nearby_pgs)
      @site = site
      @base = site.source
      @dir  = "attraction/#{at['slug']}"
      @name = 'index.html'

      self.process(@name)
      self.read_yaml(File.join(@base, '_layouts'), 'attraction.html')
      self.data.merge!(at)
      self.data['layout']        = 'attraction'
      self.data['facilityName']  = at['name']
      self.data['title']         = "#{at['name']} 아이랑 갈만한 곳"
      self.data['description']   = build_at_desc(at)
      self.data['nearby_ats']    = nearby_ats.map { |a| slim_at(a) }
      self.data['nearby_pgs']    = nearby_pgs.map { |p| slim_pg(p) }
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

    def slim_pg(p)
      { 'slug' => p['slug'], 'facilityName' => p['name'],
        'address' => p['address'], 'instlPlace' => p['instlPlace'],
        'safetyStatus' => p['safetyStatus'] }
    end
  end

  # ── 지역별 페이지 ──────────────────────
  class RegionPage < Page
    def initialize(site, sido, sigungu, playgrounds, attractions)
      @site = site
      @base = site.source

      slug_sido = sido.gsub(/\s+/, '')
      if sigungu.to_s.strip.empty?
        @dir = "region/#{slug_sido}"
        title_loc = sido
      else
        @dir = "region/#{slug_sido}/#{sigungu.gsub(/\s+/, '')}"
        title_loc = "#{sido} #{sigungu}"
      end
      @name = 'index.html'

      self.process(@name)
      self.read_yaml(File.join(@base, '_layouts'), 'region.html')
      self.data['layout']      = 'region'
      self.data['sido']        = sido
      self.data['sigungu']     = sigungu.to_s
      self.data['title']       = "#{title_loc} 아이랑 갈만한 곳"
      self.data['description'] = "#{title_loc} 어린이 놀이시설 #{playgrounds.size}개, 관광지 #{attractions.size}개 정보. 안전검사 현황 포함."
      self.data['playgrounds'] = playgrounds.first(60).map do |p|
        { 'slug' => p['slug'], 'facilityName' => p['name'],
          'address' => p['address'], 'sigungu' => p['sigungu'],
          'instlPlace' => p['instlPlace'], 'safetyStatus' => p['safetyStatus'] }
      end
      self.data['attractions'] = attractions.first(40).map do |a|
        { 'slug' => a['slug'], 'facilityName' => a['name'],
          'address' => a['address'], 'contentType' => a['contentType'],
          'contentTypeLabel' => a['contentTypeLabel'] }
      end
      self.data['pg_count']    = playgrounds.size
      self.data['at_count']    = attractions.size
    end
  end

  # ── 검색 인덱스 ──────────────────────
  class SearchIndexPage < Page
    def initialize(site, playgrounds, attractions)
      @site = site
      @base = site.source
      @dir  = ''
      @name = 'search_index.json'

      self.process(@name)
      self.data = { 'layout' => nil, 'sitemap' => false }

      pg_index = playgrounds.map do |pg|
        { 'type' => 'playground', 'slug' => pg['slug'],
          'name' => pg['name'], 'sido' => pg['sido'],
          'sigungu' => pg['sigungu'], 'address' => pg['address'],
          'instlPlace' => pg['instlPlace'], 'safetyStatus' => pg['safetyStatus'] }
      end

      at_index = attractions.map do |at|
        { 'type' => 'attraction', 'slug' => at['slug'],
          'name' => at['name'], 'sido' => at['sido'],
          'address' => at['address'], 'typeLabel' => at['contentTypeLabel'],
          'firstImage' => at['firstImage'] }
      end

      self.content = (pg_index + at_index).to_json
    end

    def output   = self.content
    def render(layouts, registers); end
  end
end
