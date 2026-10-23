# frozen_string_literal: true

# Explicit example order for one rspec process.
# Examples take their index in ENV["ids"]. A group takes the minimum rank of
# its descendants. Ids that are not listed sort after every listed id, keeping
# their original relative order.

RSpec.configure do |config|
  positions = {}
  raw = ENV.fetch("ids", "")
  # A single environment value cannot hold every id. The file is the same list.
  file_name = ENV.fetch("ids_file", "")
  raw = File.read(file_name) if raw.empty? && !file_name.empty?
  raw.split(/\s+/).each_with_index do |ident, index|
    positions[ident] = index unless ident.empty?
  end
  fallback = positions.size

  rank = nil
  rank = lambda do |item|
    if item.respond_to?(:descendant_filtered_examples)
      descendants = item.descendant_filtered_examples
      next fallback if descendants.nil? || descendants.empty?

      next descendants.map { |child| rank.call(child) }.min
    end
    positions.fetch(item.id, fallback)
  end

  config.register_ordering(:global) do |items|
    items.each_with_index.sort_by { |item, index| [rank.call(item), index] }.map(&:first)
  end
end
