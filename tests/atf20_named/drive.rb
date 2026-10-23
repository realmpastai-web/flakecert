# frozen_string_literal: true

require "json"
require "open3"
require "tmpdir"

module Drive
  ROOT = File.expand_path("../..", __dir__)
  PRELUDE = File.join(ROOT, "atf20", "argv_prelude.rb")

  module_function

  def hook_path
    ENV["ATF20_HOOK"] || File.join(ROOT, "atf20", "atf20_hook.rb")
  end

  def child_env(extra)
    env = {}
    %w[PATH HOME GEM_HOME GEM_PATH GEM_SPEC_CACHE LANG LC_ALL].each do |key|
      env[key] = ENV[key] if ENV[key]
    end
    env.merge(extra)
  end

  def run_spec(spec, target, n: nil, pass_flag: false)
    Dir.mktmpdir("atf20-drive") do |dir|
      out = File.join(dir, "verdict.json")
      audit = File.join(dir, "audit.json")
      marker = File.join(dir, "marker.txt")
      args = [
        "--format", "documentation",
        "--no-color",
        "--require", hook_path,
        "--atf-case", "fixture",
        "--atf-commit", "0" * 40,
        "--atf-tarball", "0" * 64,
        "--atf-target", target,
        "--atf-out", out,
        "--atf-audit", audit,
        "--atf-args", JSON.generate([spec]),
      ]
      args.push("--atf-n", n.to_s) unless n.nil?
      args << spec
      env = child_env(
        "RUBYOPT" => "-r#{PRELUDE}",
        "ATF_MARKER" => marker,
      )
      cmd = [
        "ruby", "-rrspec/core", "-e",
        "status = RSpec::Core::Runner.run(ARGV, $stderr, $stdout).to_i; exit(status)",
        "--", *args,
      ]
      stdout, status = Open3.capture2e(env, *cmd)
      parsed = File.exist?(out) ? JSON.parse(File.read(out)) : nil
      audit_parsed = File.exist?(audit) ? JSON.parse(File.read(audit)) : nil
      marker_text = File.exist?(marker) ? File.read(marker) : ""
      {
        "stdout" => stdout,
        "exit" => status.exitstatus,
        "verdict" => parsed,
        "audit" => audit_parsed,
        "marker" => marker_text,
      }
    end
  end

  def fail!(name, detail)
    warn "#{name} FAIL #{detail}"
    exit 1
  end

  def p2!
    name = "test_p2_stops_at_first_failure"
    spec = File.join(ROOT, "tests/fixtures/atf20/p2_spec.rb")
    result = run_spec(spec, "p2_spec.rb:2", n: 4)
    $stdout.puts result["stdout"]
    verdict = result["verdict"]
    rows = verdict && verdict["executions"]
    unless result["exit"] == 1 && verdict && verdict["verdict"] == "FAIL" && rows.is_a?(Array) && rows.length == 1 && rows[0]["status"] == "failed"
      fail!(name, "exit=#{result['exit']} verdict=#{verdict.inspect}")
    end
    puts "#{name} PASS executions=1"
  end

  def p3!
    name = "test_p3_in_process_not_relaunch"
    spec = File.join(ROOT, "tests/fixtures/atf20/p3_spec.rb")
    result = run_spec(spec, "p3_spec.rb:2", n: 3)
    $stdout.puts result["stdout"]
    verdict = result["verdict"]
    audit = result["audit"]
    rows = verdict && verdict["executions"]
    lines = result["marker"].lines.map(&:strip).reject(&:empty?)
    pids = lines.map { |line| line.split.first }
    counts = lines.map { |line| line.split[1].to_i }
    text = JSON.generate(verdict)
    problems = []
    problems << "verdict" unless verdict && verdict["verdict"] == "PASS" && rows.is_a?(Array) && rows.length == 3
    problems << "statuses" unless rows && rows.all? { |row| row["status"] == "passed" }
    problems << "exit" unless result["exit"] == 0
    problems << "pids" unless pids.length == 3 && pids.uniq.length == 1
    problems << "counts" unless counts == [1, 2, 3]
    problems << "audit" unless audit && audit["audit_only"] == true && audit["order"].is_a?(Array) && audit["order"].length == 1
    problems << "forbidden" if text.match?(/seed|order/i)
    problems << "bound" unless result["stdout"].include?("clopper_pearson_95_upper_0_of_20=0.139108")
    problems << "min_n" unless result["stdout"].include?("min_n_for_1pct=299")
    problems << "wording" unless result["stdout"].include?("report_wording=Fixed")
    problems << "field" if verdict && verdict["verdict"] == "Fixed"
    unless problems.empty?
      fail!(name, "problems=#{problems.join(',')} exit=#{result['exit']} marker=#{result['marker'].inspect} verdict=#{verdict.inspect} audit=#{audit.inspect}")
    end
    puts "#{name} PASS executions=3 pid=#{pids[0]}"
  end

  def p1!
    name = "test_p1_default_n_is_20"
    spec = File.join(ROOT, "tests/fixtures/atf20/pass_spec.rb")
    result = run_spec(spec, "pass_spec.rb:2", n: nil)
    $stdout.puts result["stdout"]
    verdict = result["verdict"]
    rows = verdict && verdict["executions"]
    readings = verdict && verdict["readings"]
    unless result["exit"] == 0 && verdict && verdict["n"] == 20 && verdict["verdict"] == "PASS" && rows&.length == 20
      fail!(name, "exit=#{result['exit']} verdict=#{verdict.inspect}")
    end
    unless readings == [{"n" => 20, "verdict" => "PASS"}, {"n" => 21, "verdict" => "UNOBSERVED"}]
      fail!(name, "readings=#{readings.inspect}")
    end
    puts "#{name} PASS n=20"
  end

  def n_flag!
    name = "test_p1_atf_n_flag"
    spec = File.join(ROOT, "tests/fixtures/atf20/pass_spec.rb")
    result = run_spec(spec, "pass_spec.rb:2", n: 2)
    $stdout.puts result["stdout"]
    verdict = result["verdict"]
    rows = verdict && verdict["executions"]
    unless result["exit"] == 0 && verdict && verdict["n"] == 2 && verdict["verdict"] == "PASS" && rows&.length == 2
      fail!(name, "exit=#{result['exit']} verdict=#{verdict.inspect}")
    end
    puts "#{name} PASS executions=2"
  end
end
