FROM ruby@sha256:2e32876dfe84913ec84eb4a59617f72dab7c0989d38f8219487491e384543975

WORKDIR /app
COPY inputs/flakecert-rspec-runner/sample/ /app/
COPY envs/rspec/Gemfile.lock /app/Gemfile.lock
RUN bundle install --frozen
COPY flakecert/runners/srand.rb /flakecert/srand.rb
