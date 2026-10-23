# frozen_string_literal: true

# Minitest ordering shim for QueueTrail-Rails replay.
# Behaviour is specified in docs/QUEUETRAIL-RAILS-SPEC.md.
# This file does not load minitest, activesupport, railties, or Rails.

module QueueTrailRailsOrder
  module_function

  def parse_ids(raw)
    raw.to_s.split(/\s+/).reject(&:empty?)
  end

  def load_ids
    raw = ENV.fetch("ids", "")
    if raw.empty?
      file_name = ENV.fetch("ids_file", "")
      raw = File.read(file_name) if !file_name.empty?
    end
    parse_ids(raw)
  end

  def apply_srand!
    raw = ENV["QUEUETRAIL_SRAND"]
    return if raw.nil? || raw.empty?

    srand(Integer(raw))
  end

  def constant_for(name)
    name.split("::").reject(&:empty?).inject(Object) do |namespace, piece|
      namespace.const_get(piece)
    end
  end

  def install!
    return if @installed
    return unless defined?(::Minitest)

    ::Minitest.singleton_class.prepend(RunAll)
    @installed = true
  end

  def wrap_require!
    return if @require_wrapped

    kernel = Module.new do
      def require(name)
        loaded = super
        QueueTrailRailsOrder.install!
        loaded
      end
      private :require
    end
    Kernel.prepend(kernel)
    @require_wrapped = true
  end

  module RunAll
    def run_all_suites(reporter, _options = nil)
      QueueTrailRailsOrder.apply_srand!
      QueueTrailRailsOrder.load_ids.each do |ident|
        klass_name, method_name = ident.split("#", 2)
        raise ArgumentError, "id has no method: #{ident}" if method_name.nil? || method_name.empty?

        klass = QueueTrailRailsOrder.constant_for(klass_name)
        reporter.prerecord(klass, method_name) if reporter.respond_to?(:prerecord)
        result = klass.new(method_name).run
        reporter.record(result) if reporter.respond_to?(:record)
      end
    end
  end
end

QueueTrailRailsOrder.wrap_require!
QueueTrailRailsOrder.install!
