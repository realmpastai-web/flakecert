# frozen_string_literal: true

# Clean-room policy model. Loaded with --require.
# P1: at most N executions, default 20 (--atf-n / ATF_N).
# P2: stop after the first failed execution.
# P3: those executions call the example in this process.
# P4: PASS only when every execution passed; otherwise FAIL.
# P5: the verdict file has no seed and no order. The audit file records
#     the example ids and is marked audit_only.
# P6: PASS is reported with Fixed wording only on the report stream,
#     never in the verdict field.
# P7: a PASS prints the one-sided exact 95% upper bound for 0/20 and the
#     smallest N whose bound is at most 1%.

require "fileutils"
require "json"

module Atf20
  DEFAULT_N = 20

  module Policy
    def self.executions(max_attempts, stop_on_first_failure: true)
      rows = []
      max_attempts.times do |offset|
        status, exception_class, first_line = yield(offset)
        rows << {
          "i" => offset + 1,
          "status" => status,
          "exception_class" => exception_class,
          "first_line" => first_line,
        }
        break if stop_on_first_failure && status != "passed"
      end
      verdict = rows.all? { |row| row["status"] == "passed" } && !rows.empty? ? "PASS" : "FAIL"
      [rows, verdict]
    end

    def self.readings(rows, max_attempts)
      [20, 21].map do |reading_n|
        {"n" => reading_n, "verdict" => reading_for(rows, max_attempts, reading_n)}
      end
    end

    def self.reading_for(rows, max_attempts, reading_n)
      return "FAIL" if rows.any? { |row| row["status"] != "passed" }
      return "PASS" if rows.length >= reading_n && reading_n <= max_attempts
      "UNOBSERVED"
    end
  end

  module Bound
    def self.upper(n, alpha = 0.05)
      lo = 0.0
      hi = 1.0
      80.times do
        mid = (lo + hi) / 2.0
        if (1.0 - mid)**n > alpha
          lo = mid
        else
          hi = mid
        end
      end
      (lo + hi) / 2.0
    end

    def self.min_n_for(limit, alpha = 0.05)
      n = 1
      n += 1 until upper(n, alpha) <= limit
      n
    end
  end

  class << self
    def run_once(example)
      example.run # in_process
    end

    def capture(example)
      err = example.exception
      if err
        line = err.message.to_s.lines.first
        return ["failed", err.class.name, line&.strip]
      end
      if example.pending? || example.skipped?
        return ["pending", nil, nil]
      end
      ["passed", nil, nil]
    end

    def target?(example)
      spec = ENV["ATF_TARGET"].to_s
      return false if spec.empty?
      file, line = spec.split(":", 2)
      meta = example.metadata
      location = meta[:location].to_s
      return true if location.end_with?("#{file}:#{line}")
      paths = [location, meta[:file_path].to_s, meta[:absolute_file_path].to_s]
      paths.any? { |item| item.include?(file) } && meta[:line_number].to_s == line.to_s
    end

    def limit
      raw = (ENV["ATF_N"] || DEFAULT_N.to_s).to_i
      raw.positive? ? raw : DEFAULT_N
    end

    def verdict_args
      raw = ENV["ATF_ARGS"]
      list = raw && !raw.empty? ? JSON.parse(raw) : []
      list.map(&:to_s).reject { |item| item.match?(/seed|order/i) }
    end

    def report(line)
      stream = @report_stream ||= $stderr
      stream.puts(line)
      stream.flush
    end

    def observe(example)
      @order ||= []
      @order << example.id
    end

    def retry_target(example)
      n = limit
      rows, verdict = Policy.executions(n, stop_on_first_failure: true) do |_offset|
        run_once(example)
        capture(example)
      end
      @result = {"rows" => rows, "verdict" => verdict, "n" => n}
      rows.each do |row|
        report("atf20 i=#{row['i']} status=#{row['status']}")
      end
      report("atf20 verdict=#{verdict}")
      Policy.readings(rows, n).each do |reading|
        report("reading_n=#{reading['n']} verdict=#{reading['verdict']}")
      end
      return unless verdict == "PASS"

      report(format("clopper_pearson_95_upper_0_of_20=%.6f", Bound.upper(20)))
      report(format("clopper_pearson_95_upper_0_of_%d=%.6f", rows.length, Bound.upper(rows.length)))
      report("min_n_for_1pct=#{Bound.min_n_for(0.01)}")
      report("report_wording=Fixed")
    end

    def finish!
      n = @result ? @result["n"] : limit
      rows = @result ? @result["rows"] : []
      verdict = @result ? @result["verdict"] : "FAIL"
      if @result.nil?
        report("atf20 target_missing=1")
        report("atf20 verdict=FAIL")
      end
      payload = {
        "case" => ENV["ATF_CASE"] || "unset",
        "commit" => ENV["ATF_COMMIT"] || "",
        "tarball_sha256" => ENV["ATF_TARBALL_SHA256"] || "",
        "args" => verdict_args,
        "n" => n,
        "executions" => rows,
        "verdict" => verdict,
        "readings" => Policy.readings(rows, n),
      }
      text = JSON.pretty_generate(payload) + "\n"
      if text.match?(/seed|order/i)
        report("verdict_json_forbidden=1")
        write_text(out_path, text)
        raise "verdict file contains a forbidden token"
      end
      write_text(out_path, text)
      audit = {
        "audit_only" => true,
        "case" => payload["case"],
        "order" => @order || [],
      }
      write_text(audit_path, JSON.pretty_generate(audit) + "\n")
    end

    def out_path
      ENV["ATF_OUT"] || File.join("atf20", "out", "#{(ENV['ATF_CASE'] || 'case')}.json")
    end

    def audit_path
      ENV["ATF_AUDIT"] || File.join("atf20", "out", "#{(ENV['ATF_CASE'] || 'case')}.audit.json")
    end

    def write_text(path, text)
      FileUtils.mkdir_p(File.dirname(path))
      File.write(path, text)
    end

    def install!
      return if @installed
      @installed = true
      RSpec.configure do |config|
        config.around(:example) do |ex|
          Atf20.observe(ex)
          if Atf20.target?(ex)
            Atf20.retry_target(ex)
          else
            ex.run
          end
        end
        config.after(:suite) { Atf20.finish! }
      end
    end
  end
end

Atf20.install! if defined?(RSpec)
