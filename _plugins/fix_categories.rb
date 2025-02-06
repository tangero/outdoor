module Jekyll
  Hooks.register :posts, :pre_render do |post|
    if post.data["categories"].is_a?(String)
      post.data["categories"] = [post.data["categories"]]
    end
  end
end 