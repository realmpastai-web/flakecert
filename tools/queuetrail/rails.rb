# frozen_string_literal: true

# Opt-in QueueTrail hook for Rails parallel tests.
# Behaviour is specified in docs/QUEUETRAIL-RAILS-SPEC.md.
# This file does not load activesupport, railties, minitest, or Rails.

require "fileutils"
require "json"
require "securerandom"
require "socket"

module QueueTrailRails
  MASTER_FACTOR = 1_000_003
  WORKER_FACTOR = 9_176
  MODULUS = 1 << 31

  module_function

  def ensure_run_id!
    current = ENV["QUEUETRAIL_RUN_ID"]
    return current if current && !current.empty?

    ENV["QUEUETRAIL_RUN_ID"] = SecureRandom.hex(8)
  end

  def master_seed
    raw = ENV.fetch("QUEUETRAIL_MASTER_SEED", "0")
    raise ArgumentError, "QUEUETRAIL_MASTER_SEED must be a non-negative integer" unless /\A\d+\z/.match?(raw)

    Integer(raw)
  end

  def srand_seed(worker_num)
    worker = Integer(worker_num)
    raise ArgumentError, "worker number must be a non-negative integer" if worker.negative?

    ((master_seed + 1) * MASTER_FACTOR + worker * WORKER_FACTOR) % MODULUS
  end

  def trail_dir
    expanded = File.expand_path(ENV.fetch("QUEUETRAIL_DIR", "queuetrail"))
    temporary = File.expand_path("/tmp")
    if expanded == temporary || expanded.start_with?(temporary + File::SEPARATOR)
      raise ArgumentError, "QueueTrail refuses to write under /tmp"
    end
    expanded
  end

  def minitest_seed
    return nil unless defined?(::Minitest)
    return nil unless ::Minitest.respond_to?(:seed)

    ::Minitest.seed
  end

  def test_queue_version
    raw = ENV["QUEUETRAIL_TEST_QUEUE_VERSION"]
    return nil if raw.nil? || raw.empty?

    raw
  end

  def write_line(path, payload)
    File.open(path, "a") do |handle|
      handle.write(JSON.generate(payload))
      handle.write("\n")
    end
  end

  def start_worker(worker_num)
    seed = srand_seed(worker_num)
    directory = trail_dir
    srand(seed)
    FileUtils.mkdir_p(directory)
    path = File.join(directory, format("worker-%d.jsonl", Integer(worker_num)))
    ENV["QUEUETRAIL_WORKER_PATH"] = path
    @index = 0
    write_line(
      path,
      {
        "type" => "worker",
        "run_id" => ensure_run_id!,
        "worker_num" => Integer(worker_num),
        "pid" => Process.pid,
        "host" => Socket.gethostname,
        "srand_seed" => seed,
        "minitest_seed" => minitest_seed,
        "master_seed" => master_seed,
        "ruby_version" => RUBY_VERSION,
        "rspec_seed" => nil,
        "test_queue_version" => test_queue_version,
      },
    )
    path
  end

  def status_of(result)
    return "skip" if result.respond_to?(:skipped?) && result.skipped?
    return "error" if result.respond_to?(:error?) && result.error?
    return "pass" if result.respond_to?(:passed?) && result.passed?

    "fail"
  end

  def record_result(klass, method, result, start_mono, finish_mono)
    path = ENV["QUEUETRAIL_WORKER_PATH"]
    raise "QueueTrail suite observed before worker start" if path.nil? || path.empty?

    index = @index || 0
    @index = index + 1
    write_line(
      path,
      {
        "type" => "suite",
        "index" => index,
        "name" => "#{klass}##{method}",
        "path" => "",
        "start_monotonic" => start_mono,
        "end_monotonic" => finish_mono,
        "status" => status_of(result),
      },
    )
  end

  def install!
    return if @installed
    return unless defined?(::ActiveSupport::TestCase) && ::ActiveSupport::TestCase.respond_to?(:parallelize_setup)
    return unless defined?(::ActiveSupport::Testing::Parallelization::Worker)

    ::ActiveSupport::TestCase.parallelize_setup do |worker_num|
      QueueTrailRails.start_worker(worker_num)
    end
    ::ActiveSupport::Testing::Parallelization::Worker.prepend(PerformJob)
    @installed = true
  end

  module PerformJob
    def perform_job(job)
      @queuetrail_job = job
      @queuetrail_seen = false
      @queuetrail_start = Process.clock_gettime(Process::CLOCK_MONOTONIC)
      ensure_record_wrapper!
      super
      return unless @queuetrail_seen

      finish = Process.clock_gettime(Process::CLOCK_MONOTONIC)
      QueueTrailRails.record_result(job[0], job[1], @queuetrail_result, @queuetrail_start, finish)
    end

    def ensure_record_wrapper!
      queue = @queue
      return if queue.nil?
      return unless queue.respond_to?(:record)
      return if queue.instance_variable_get(:@queuetrail_wrapped)

      worker = self
      original = queue.method(:record)
      queue.define_singleton_method(:record) do |reporter, result|
        worker.instance_variable_set(:@queuetrail_result, result)
        worker.instance_variable_set(:@queuetrail_seen, true)
        original.call(reporter, result)
      end
      queue.instance_variable_set(:@queuetrail_wrapped, true)
    end
  end
end

QueueTrailRails.ensure_run_id!
QueueTrailRails.install!
