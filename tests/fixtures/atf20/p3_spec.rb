RSpec.describe "in process" do
  it "records the process" do
    path = ENV.fetch("ATF_MARKER")
    count = File.exist?(path) ? File.read(path).lines.length : 0
    File.open(path, "a") do |handle|
      handle.puts("#{Process.pid} #{count + 1}")
      handle.flush
    end
  end
end
