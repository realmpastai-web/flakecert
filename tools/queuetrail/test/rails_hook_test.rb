# frozen_string_literal: true

# Stub-only tests for the QueueTrail-Rails hook. Does not load Rails,
# activesupport, railties, or minitest.

require "json"
require "tmpdir"

HOOK = File.expand_path("../rails.rb", __dir__)
SHIM = File.expand_path("../rails_order_shim.rb", __dir__)

def expected_seed(master, worker)
  ((master + 1) * 1_000_003 + worker * 9_176) % (1 << 31)
end

def assert_ok(condition, message)
  abort(message) unless condition
end

unloaded = Dir.mktmpdir("qtr-unloaded", "/var/tmp")
unloaded_script = "abort('trail dir created') if Dir.exist?('queuetrail')"
assert_ok(system("ruby", "-C", unloaded, "-e", unloaded_script), "RR1 unloaded process failed")

module ActiveSupport
  class TestCase
    def self.parallelize_setup(&block)
      @parallel_hooks ||= []
      @parallel_hooks << block
    end

    def self.parallel_hooks
      @parallel_hooks || []
    end
  end

  module Testing
    class Parallelization
      class Worker
        def initialize(number)
          @number = number
          @queue = QueueDouble.new
        end

        def titles
          @titles ||= []
        end

        def set_process_title(status)
          titles << status
          status
        end

        # Copies worker.rb perform_job: with_info_handler, then
        # run_one_method when that method exists, otherwise klass.new(method).run,
        # then @queue.record. The return value is the process title, not the result.
        def perform_job(job)
          klass = job[0]
          method = job[1]
          reporter = job[2]
          set_process_title("#{klass}##{method}")
          result = klass.with_info_handler(reporter) do
            if defined?(Minitest) && Minitest.respond_to?(:run_one_method)
              Minitest.run_one_method(klass, method)
            else
              klass.new(method).run
            end
          end
          safe_record(reporter, result)
        end

        def safe_record(reporter, result)
          @queue.record(reporter, result)
          set_process_title("(idle)")
        end
      end
    end
  end
end

class QueueDouble
  attr_reader :recorded

  def record(_reporter, result)
    @recorded = result
  end
end

class StubResult
  def initialize(skipped: false, error: false, passed: false)
    @skipped = skipped
    @error = error
    @passed = passed
  end

  def skipped?
    @skipped
  end

  def error?
    @error
  end

  def passed?
    @passed
  end
end

class ExampleTest
  def self.with_info_handler(_reporter)
    yield
  end

  def initialize(method)
    @method = method
  end

  def run
    case @method
    when "test_fail"
      StubResult.new(passed: true)
    when "test_pass"
      StubResult.new(error: true)
    when "test_skip"
      StubResult.new(skipped: true)
    else
      StubResult.new
    end
  end
end

module Minitest
  def self.seed
    99
  end
end

trail = Dir.mktmpdir("qtr-rails", "/var/tmp")
ENV["QUEUETRAIL_DIR"] = trail
ENV["QUEUETRAIL_MASTER_SEED"] = "42"
ENV["QUEUETRAIL_RUN_ID"] = "rails-run"
ENV.delete("QUEUETRAIL_TEST_QUEUE_VERSION")

require HOOK

assert_ok(!File.exist?(File.join(trail, "worker-3.jsonl")), "RR1 loaded hook created a trail before worker start")
assert_ok(ActiveSupport::TestCase.parallel_hooks.length == 1, "RR1 parallelize_setup was not registered")

ActiveSupport::TestCase.parallel_hooks.each { |hook| hook.call(3) }
observed = srand(0)
assert_ok(observed == expected_seed(42, 3), "RR3 seed #{observed} != #{expected_seed(42, 3)}")

worker = ActiveSupport::Testing::Parallelization::Worker.new(3)
reporter = Object.new
[
  "test_fail",
  "test_pass",
  "test_skip",
  "test_bad",
].each do |method|
  worker.perform_job([ExampleTest, method, reporter])
end

def Minitest.run_one_method(klass, method)
  klass.new(method).run
end

worker.perform_job([ExampleTest, "test_fail", reporter])

lines = File.readlines(File.join(trail, "worker-3.jsonl"), chomp: true)
assert_ok(lines.length == 6, "RR2 expected 6 jsonl lines, got #{lines.length}")
header = JSON.parse(lines[0])
assert_ok(header["type"] == "worker", "header type")
assert_ok(header["run_id"] == "rails-run", "run_id")
assert_ok(header["worker_num"] == 3, "worker_num")
assert_ok(header["pid"] == Process.pid, "pid")
assert_ok(header["host"].is_a?(String) && !header["host"].empty?, "host")
assert_ok(header["srand_seed"] == expected_seed(42, 3), "srand_seed field")
assert_ok(header["minitest_seed"] == 99, "minitest_seed")
assert_ok(header["master_seed"] == 42, "master_seed")
assert_ok(header["ruby_version"] == RUBY_VERSION, "ruby_version")
assert_ok(header["rspec_seed"].nil?, "rspec_seed")
assert_ok(header["test_queue_version"].nil?, "test_queue_version")

suites = lines.drop(1).map { |line| JSON.parse(line) }
assert_ok(
  suites.map { |row| row["name"] } == [
    "ExampleTest#test_fail",
    "ExampleTest#test_pass",
    "ExampleTest#test_skip",
    "ExampleTest#test_bad",
    "ExampleTest#test_fail",
  ],
  "RR2 suite order",
)
assert_ok(suites.map { |row| row["index"] } == [0, 1, 2, 3, 4], "RR2 indexes")
assert_ok(
  suites.map { |row| row["status"] } == %w[pass error skip fail pass],
  "RR2 status is read from the result, got #{suites.map { |row| row['status'] }}",
)
assert_ok(suites.all? { |row| row["path"] == "" }, "RR2 path")
assert_ok(suites[0]["end_monotonic"] >= suites[0]["start_monotonic"], "monotonic")
assert_ok(worker.titles.include?("(idle)"), "stub perform_job returns through set_process_title")

forbidden = "/tmp/queuetrail-rails-refuse-#{Process.pid}"
refuse = <<~RUBY
  ENV["QUEUETRAIL_DIR"] = #{forbidden.inspect}
  ENV["QUEUETRAIL_MASTER_SEED"] = "0"
  ENV["QUEUETRAIL_RUN_ID"] = "refuse"
  module ActiveSupport
    class TestCase
      def self.parallelize_setup(&block)
        @parallel_hooks ||= []
        @parallel_hooks << block
      end
      def self.parallel_hooks
        @parallel_hooks || []
      end
    end
    module Testing
      class Parallelization
        class Worker
          def perform_job(_job); end
        end
      end
    end
  end
  require #{HOOK.inspect}
  begin
    ActiveSupport::TestCase.parallel_hooks.each { |hook| hook.call(1) }
  rescue ArgumentError
    exit 0
  end
  exit 1
RUBY
assert_ok(system("ruby", "-e", refuse), "RR2 /tmp refusal failed")
assert_ok(!File.exist?(File.join(forbidden, "worker-1.jsonl")), "RR2 wrote a trail under /tmp")

assert_ok(expected_seed(0, 0) == 1_000_003, "RR3 k=0")
assert_ok(expected_seed(0, 1) == 1_009_179, "RR3 k=1")

shim_dir = Dir.mktmpdir("qtr-shim", "/var/tmp")
shim_script = <<~RUBY
  $ran = []
  module Minitest
    def self.run_all_suites(*)
      abort("original shuffle ran")
    end
  end
  class Alpha
    def initialize(method)
      @method = method
    end
    def run
      $ran << ("Alpha#" + @method)
      :alpha
    end
  end
  class Beta
    def initialize(method)
      @method = method
    end
    def run
      $ran << ("Beta#" + @method)
      :beta
    end
  end
  class Reporter
    attr_reader :records
    def initialize
      @records = []
    end
    def prerecord(_klass, _method); end
    def record(result)
      @records << result
    end
  end
  ENV["ids"] = "Alpha#test_one Beta#test_two"
  ENV["QUEUETRAIL_SRAND"] = "1000003"
  require #{SHIM.inspect}
  reporter = Reporter.new
  Minitest.run_all_suites(reporter, nil)
  abort($ran.inspect) unless $ran == ["Alpha#test_one", "Beta#test_two"]
  abort(reporter.records.inspect) unless reporter.records == [:alpha, :beta]
  abort("srand") unless srand(0) == 1_000_003
  puts "SHIM_OK"
RUBY
shim_run = IO.popen(["ruby", "-C", shim_dir, "-e", shim_script], &:read)
assert_ok($?.success? && shim_run.include?("SHIM_OK"), "RR4 shim failed: #{shim_run}")

deferred = <<~RUBY
  ENV["ids"] = "Alpha#test_one"
  ENV["QUEUETRAIL_SRAND"] = "1000003"
  require #{SHIM.inspect}
  stub = File.join(#{shim_dir.inspect}, "minitest_stub.rb")
  File.write(stub, <<~'STUB')
    module Minitest
      def self.run_all_suites(*)
        abort("original shuffle ran")
      end
    end
    class Alpha
      def initialize(method)
        @method = method
      end
      def run
        @method
      end
    end
  STUB
  require stub
  Minitest.run_all_suites(Object.new)
  puts "DEFER_OK"
RUBY
defer_run = IO.popen(["ruby", "-e", deferred], &:read)
assert_ok($?.success? && defer_run.include?("DEFER_OK"), "RR4 deferred shim failed: #{defer_run}")

puts "OK"
