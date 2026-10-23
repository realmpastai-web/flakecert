# frozen_string_literal: true

# Opt-in QueueTrail hook. Loaded with: ruby -r ./tools/queuetrail/queuetrail.rb
# Behaviour is specified in docs/QUEUETRAIL-SPEC.md. This file does not load test-queue.

require "fileutils"
require "json"
require "securerandom"
require "socket"

module QueueTrail
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

  def rspec_seed
    return nil unless defined?(::RSpec)
    return nil unless ::RSpec.respond_to?(:configuration)

    config = ::RSpec.configuration
    return nil unless config.respond_to?(:seed)

    config.seed
  end

  def test_queue_version
    raw = ENV["QUEUETRAIL_TEST_QUEUE_VERSION"]
    return nil if raw.nil? || raw.empty?

    raw
  end

  def text_or_nil(value)
    return nil if value.nil?

    text = value.to_s
    text.empty? ? nil : text
  end

  # O6 / rspec.rb:70-77. suite.name is the Ruby constant and is not a source.
  def suite_name(suite)
    if suite.respond_to?(:id)
      text = text_or_nil(suite.id)
      return text unless text.nil?
    end
    if suite.respond_to?(:full_description)
      text = text_or_nil(suite.full_description)
      return text unless text.nil?
    end
    if suite.respond_to?(:metadata) && !(meta = suite.metadata).nil?
      if meta.respond_to?(:key?) && meta.key?(:full_description)
        text = text_or_nil(meta[:full_description])
        return text unless text.nil?
      end
      if meta.respond_to?(:[])
        group = meta[:example_group]
        if !group.nil? && group.respond_to?(:[])
          text = text_or_nil(group[:full_description])
          return text unless text.nil?
        end
      end
    end
    suite.to_s
  end

  def execution_status(example)
    return nil unless example.respond_to?(:execution_result)

    result = example.execution_result
    return nil if result.nil? || !result.respond_to?(:status)

    text_or_nil(result.status)
  end

  # O7. failure_count is the example count, so status is read from examples.
  def suite_status(suite)
    statuses = []
    if suite.respond_to?(:descendant_filtered_examples)
      descendants = suite.descendant_filtered_examples
      Array(descendants).each { |example| statuses << execution_status(example) } unless descendants.nil?
    end
    statuses << execution_status(suite) if suite.respond_to?(:execution_result)
    return "unknown" if statuses.empty? || statuses.any?(&:nil?)
    return "failed" if statuses.any? { |status| status == "failed" }

    "passed"
  end

  def suite_path(suite)
    if suite.respond_to?(:path) && !suite.path.nil?
      suite.path.to_s
    elsif suite.respond_to?(:file_path) && !suite.file_path.nil?
      suite.file_path.to_s
    elsif suite.respond_to?(:metadata)
      meta = suite.metadata
      if meta.respond_to?(:[]) && !meta[:file_path].nil?
        meta[:file_path].to_s
      else
        ""
      end
    else
      ""
    end
  end

  def append_line(path, obj)
    File.open(path, "a") do |handle|
      handle.write(JSON.generate(obj))
      handle.write("\n")
    end
  end

  def open_worker(worker_num)
    seed = srand_seed(worker_num)
    trail_dir
    srand(seed)
    directory = trail_dir
    FileUtils.mkdir_p(directory)
    path = File.join(directory, format("worker-%d.jsonl", Integer(worker_num)))
    append_line(
      path,
      {
        "type" => "worker",
        "run_id" => ensure_run_id!,
        "worker_num" => Integer(worker_num),
        "pid" => Process.pid,
        "host" => Socket.gethostname,
        "srand_seed" => seed,
        "rspec_seed" => rspec_seed,
        "master_seed" => master_seed,
        "ruby_version" => RUBY_VERSION,
        "test_queue_version" => test_queue_version,
      },
    )
    path
  end

  def record_suite(index, suite, start_mono, finish_mono, status)
    path = ENV["QUEUETRAIL_WORKER_PATH"]
    raise "QueueTrail suite observed before after_fork" if path.nil? || path.empty?

    append_line(
      path,
      {
        "type" => "suite",
        "index" => index,
        "name" => suite_name(suite),
        "path" => suite_path(suite),
        "start_monotonic" => start_mono,
        "end_monotonic" => finish_mono,
        "status" => status,
      },
    )
  end

  def install!
    return if @installed
    return unless defined?(::TestQueue::Runner) && defined?(::TestQueue::Iterator)

    ::TestQueue::Runner.prepend(RunnerHook)
    ::TestQueue::Iterator.prepend(IteratorHook)
    @installed = true
  end

  module RunnerHook
    def after_fork(num)
      ENV["QUEUETRAIL_WORKER_PATH"] = QueueTrail.open_worker(num)
      super
    end
  end

  module IteratorHook
    def each
      index = 0
      super do |suite|
        start = Process.clock_gettime(Process::CLOCK_MONOTONIC)
        status = "passed"
        begin
          yield suite
          status = QueueTrail.suite_status(suite)
        rescue StandardError
          status = "failed"
          raise
        ensure
          finish = Process.clock_gettime(Process::CLOCK_MONOTONIC)
          QueueTrail.record_suite(index, suite, start, finish, status)
          index += 1
        end
      end
    end
  end
end

QueueTrail.ensure_run_id!

module Kernel
  alias_method :queuetrail_original_require, :require

  def require(path)
    loaded = queuetrail_original_require(path)
    QueueTrail.install!
    loaded
  end
  private :require
end

QueueTrail.install!
