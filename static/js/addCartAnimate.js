function addCartAnimate (element, cart_count) {
    // 获取add_cart div元素左上角的坐标
    var $add_x = element.offset().top;
    var $add_y = element.offset().left;
    // 获取show_cart div元素左上角的坐标
    var $to_x = $('#show_count').offset().top;
    var $to_y = $('#show_count').offset().left;

    // 添加成功
    $(".add_jump")
        .css({'left': $add_y + 80, 'top': $add_x + 10, 'display': 'block'})
        .stop().animate({
            'left': $to_y + 7,
            'top': $to_x + 7
        },
        "fast", function () {
            $(".add_jump").fadeOut('fast', function () {
                // 重新设置购物车总商品条目数
                $('#show_count').html(cart_count);
            });
        });
}
