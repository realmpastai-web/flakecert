# frozen_string_literal: true

# Stub-only tests for the QueueTrail hook. Does not load test-queue.
# Success prints OK and exits 0.

require "json"
require "tmpdir"

HOOK = File.expand_path("../queuetrail.rb", __dir__)

def expected_seed(master, worker)
  ((master + 1) * 1_000_003 + worker * 9_176) % (1 << 31)
end

def assert_ok(condition, message)
  abort(message) unless condition
end

# R6: a process that does not load the hook does not create a trail directory.
unloaded = Dir.mktmpdir("qt-unloaded", "/var/tmp")
unloaded_script = "abort('trail dir created') if Dir.exist?('queuetrail')"
assert_ok(system("ruby", "-C", unloaded, "-e", unloaded_script), "R6 unloaded process failed")

# Classes named like the cited API, defined before the hook loads.
module TestQueue
  class Iterator
    def initialize(suites)
      @suites = suites
    end

    def each
      @suites.each { |suite| yield suite }
    end
  end

  class Runner
    attr_reader :seen

    def after_fork(num)
      @seen = num
    end
  end
end

Example = Struct.new(:execution_result)
Result = Struct.new(:status)

# Copies rspec_ext.rb:4-6: map then length, so the count is the example count.
class GemGroup
  def initialize(id, path, examples)
    @id = id
    @path = path
    @examples = examples
  end

  def name
    raise "suite.name is the Ruby constant"
  end

  def id
    @id
  end

  def file_path
    @path
  end

  def examples
    @examples
  end

  def descendant_filtered_examples
    examples
  end

  def failure_count
    examples.map { |example| example.execution_result.status == "failed" }.length
  end
end

class SplitExample
  def id
    "./spec/split_spec.rb[1:1]"
  end

  def file_path
    "./spec/split_spec.rb"
  end

  def execution_result
    Result.new("failed")
  end

  def failure_count
    0
  end
end

class IdOnly
  def id
    "from-id"
  end

  def failure_count
    0
  end
end

trail = Dir.mktmpdir("qt-loaded", "/var/tmp")
ENV["QUEUETRAIL_DIR"] = trail
ENV["QUEUETRAIL_MASTER_SEED"] = "42"
ENV["QUEUETRAIL_RUN_ID"] = "run-test"
ENV.delete("QUEUETRAIL_TEST_QUEUE_VERSION")

require HOOK

assert_ok(!File.exist?(File.join(trail, "worker-3.jsonl")), "R6 loaded hook created a trail before after_fork")

runner = TestQueue::Runner.new
runner.after_fork(3)
assert_ok(runner.seen == 3, "after_fork did not call super")

observed = srand(0)
assert_ok(observed == expected_seed(42, 3), "R1 seed #{observed} != #{expected_seed(42, 3)}")

passed = Example.new(Result.new("passed"))
failed = Example.new(Result.new("failed"))
iterator = TestQueue::Iterator.new(
  [
    GemGroup.new("./spec/ok_spec.rb[1:1]", "./spec/ok_spec.rb", [passed, passed]),
    GemGroup.new("./spec/bad_spec.rb[1:1]", "./spec/bad_spec.rb", [passed, failed]),
    SplitExample.new,
    IdOnly.new,
  ],
)
yielded = []
iterator.each { |suite| yielded << suite }
assert_ok(yielded.length == 4, "iterator did not yield every suite")

lines = File.readlines(File.join(trail, "worker-3.jsonl"), chomp: true)
assert_ok(lines.length == 5, "R2 expected 5 jsonl lines, got #{lines.length}")
header = JSON.parse(lines[0])
assert_ok(header["type"] == "worker", "header type")
assert_ok(header["run_id"] == "run-test", "run_id")
assert_ok(header["worker_num"] == 3, "worker_num")
assert_ok(header["pid"] == Process.pid, "pid")
assert_ok(header["host"].is_a?(String) && !header["host"].empty?, "host")
assert_ok(header["srand_seed"] == expected_seed(42, 3), "srand_seed field")
assert_ok(header["rspec_seed"].nil?, "rspec_seed")
assert_ok(header["master_seed"] == 42, "master_seed")
assert_ok(header["ruby_version"] == RUBY_VERSION, "ruby_version")
assert_ok(header["test_queue_version"].nil?, "test_queue_version")
assert_ok(!trail.start_with?("/tmp/") && trail != "/tmp", "trail dir is under /tmp")

suites = lines.drop(1).map { |line| JSON.parse(line) }
assert_ok(
  suites.map { |row| row["name"] } == [
    "./spec/ok_spec.rb[1:1]",
    "./spec/bad_spec.rb[1:1]",
    "./spec/split_spec.rb[1:1]",
    "from-id",
  ],
  "R2 suite order",
)
assert_ok(suites.map { |row| row["index"] } == [0, 1, 2, 3], "R2 indexes")
assert_ok(suites.map { |row| row["status"] } == %w[passed failed failed unknown], "gem semantics: status ignores failure_count")
assert_ok(suites[0]["path"] == "./spec/ok_spec.rb", "path")
assert_ok(suites[3]["path"] == "", "id-only path")
assert_ok(suites[0]["end_monotonic"] >= suites[0]["start_monotonic"], "monotonic")
ok_group = iterator.instance_variable_get(:@suites)[0]
assert_ok(ok_group.failure_count == 2, "gem semantics stub counts examples, got #{ok_group.failure_count}")

# install! once, and Kernel#require keeps its return value and private visibility.
assert_ok(TestQueue::Runner.ancestors.count { |mod| mod == QueueTrail::RunnerHook } == 1, "runner hook once before")
assert_ok(TestQueue::Iterator.ancestors.count { |mod| mod == QueueTrail::IteratorHook } == 1, "iterator hook once before")
QueueTrail.install!
assert_ok(TestQueue::Runner.ancestors.count { |mod| mod == QueueTrail::RunnerHook } == 1, "runner hook once after")
assert_ok(TestQueue::Iterator.ancestors.count { |mod| mod == QueueTrail::IteratorHook } == 1, "iterator hook once after")
fresh = File.join(trail, "fresh_feature.rb")
File.write(fresh, "module QueueTrailFreshFeature; end\n")
assert_ok(require(fresh) == true, "require of a new file returns true")
assert_ok(require(fresh) == false, "require of a loaded file returns false")
assert_ok(require("json") == false, "require of json returns false")
unhooked = IO.popen(["ruby", "-e", "print Kernel.private_instance_methods(false).include?(:require)"], &:read)
assert_ok(unhooked == "true", "stock require is private")
assert_ok(Kernel.private_instance_methods(false).include?(:require), "hooked require stays private")
assert_ok(!Kernel.public_instance_methods(false).include?(:require), "hooked require is not public")

# Refusing /tmp writes nothing.
forbidden = "/tmp/queuetrail-refuse-#{Process.pid}"
refuse = <<~RUBY
  ENV["QUEUETRAIL_DIR"] = #{forbidden.inspect}
  ENV["QUEUETRAIL_MASTER_SEED"] = "0"
  ENV["QUEUETRAIL_RUN_ID"] = "refuse"
  module TestQueue
    class Runner
      def after_fork(num); end
    end
    class Iterator
      def each; end
    end
  end
  require #{HOOK.inspect}
  begin
    TestQueue::Runner.new.after_fork(1)
  rescue ArgumentError
    exit 0
  end
  exit 1
RUBY
assert_ok(system("ruby", "-e", refuse), "R2 /tmp refusal failed")
assert_ok(!File.exist?(File.join(forbidden, "worker-1.jsonl")), "R2 wrote a trail under /tmp")

# -r order: hook loads before TestQueue exists, then a later require installs it.
deferred_dir = Dir.mktmpdir("qt-deferred", "/var/tmp")
deferred = <<~RUBY
  ENV["QUEUETRAIL_DIR"] = #{deferred_dir.inspect}
  ENV["QUEUETRAIL_MASTER_SEED"] = "0"
  ENV["QUEUETRAIL_RUN_ID"] = "deferred"
  require #{HOOK.inspect}
  abort("trail before classes") if File.exist?(File.join(#{deferred_dir.inspect}, "worker-1.jsonl"))
  module TestQueue
    class Runner
      def after_fork(num); end
    end
    class Iterator
      def each
        yield Struct.new(:id, :file_path).new("alpha", "alpha.rb")
      end
    end
  end
  require "json"
  TestQueue::Runner.new.after_fork(1)
  TestQueue::Iterator.new.each { |_suite| }
  body = File.read(File.join(#{deferred_dir.inspect}, "worker-1.jsonl"))
  abort("deferred seed") unless body.include?('"srand_seed":#{expected_seed(0, 1)}')
  abort("deferred suite") unless body.include?('"name":"alpha"')
RUBY
assert_ok(system("ruby", "-e", deferred), "deferred install failed")

puts "OK"
